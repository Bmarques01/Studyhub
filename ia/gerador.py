"""Conversa com o Claude (API da Anthropic) para gerar questões e flashcards a partir de um material.

Como funciona:
1. Montamos o pedido: o material (PDF dos slides ou texto) + o que gerar.
2. Pedimos a resposta num formato fixo (JSON com um "esquema"): assim ela sempre vem
   organizada, com o tipo de cada questão, as alternativas, a certa etc.
3. Transformamos esse JSON no MESMO texto da importação (P: / A) ... * / R: / E: e F: / V:).
   Assim a revisão usa os leitores que já existem, e a Bruna pode editar o texto antes de salvar.

Dois jeitos de falar com o Claude (IA_MODO no .env):
- "assinatura" (padrão): pelo Claude Code do computador, gastando o limite do plano (ia/assinatura.py).
- "api": pela API paga por uso; a chave vem do .env (ANTHROPIC_API_KEY) e nunca vai para o navegador.
"""
import base64
import json
import os
import re
from html.parser import HTMLParser
from decimal import Decimal

import anthropic

from . import assinatura

from flashcards.importacao import MARCADOR as MARCADOR_CARTAO
from questoes.importacao import ALTERNATIVA, MARCA_DE_CERTA, MARCADOR as MARCADOR_QUESTAO

MODELO = 'claude-opus-5-5'
MAX_TOKENS = 32000  # teto da resposta (com folga para 30 questões + 50 cartões)

# Preço em dólares por 1 milhão de tokens: (entrada, saída). Se o Opus recusar o pedido,
# o "fallback" pode responder com outro modelo, por isso há mais de um aqui.
PRECOS = {
    'claude-opus-5-5': (Decimal('4'), Decimal('20')),
    'claude-opus-5': (Decimal('5'), Decimal('25')),
    'claude-opus-4-8': (Decimal('5'), Decimal('25')),
}

TIPOS = {'multipla': 'múltipla escolha (4 alternativas, só uma certa)',
         'vf': 'verdadeiro ou falso',
         'aberta': 'aberta (resposta curta escrita)'}


class ErroDaIA(Exception):
    """Algo deu errado ao gerar: a mensagem já é para mostrar à Bruna."""


# ===== O "esquema": o formato exato que pedimos para a resposta =====

ESQUEMA = {
    'type': 'object',
    'properties': {
        'questoes': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'tipo': {'type': 'string', 'enum': list(TIPOS)},
                    'enunciado': {'type': 'string'},
                    'alternativas': {  # só na múltipla escolha (nas outras: lista vazia)
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {'texto': {'type': 'string'}, 'correta': {'type': 'boolean'}},
                            'required': ['texto', 'correta'],
                            'additionalProperties': False,
                        },
                    },
                    'resposta': {'type': 'string'},  # V/F: "V" ou "F"; aberta: a resposta esperada
                    'explicacao': {'type': 'string'},
                },
                'required': ['tipo', 'enunciado', 'alternativas', 'resposta', 'explicacao'],
                'additionalProperties': False,
            },
        },
        'flashcards': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'frente': {'type': 'string'}, 'verso': {'type': 'string'}},
                'required': ['frente', 'verso'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['questoes', 'flashcards'],
    'additionalProperties': False,
}

SISTEMA = """Você cria material de estudo para uma estudante brasileira de Ciência da Computação, \
a partir do material de aula que ela envia (slides ou texto).

Regras:
- Escreva em português do Brasil, com linguagem clara.
- Baseie-se no material enviado. Cubra os pontos mais importantes, sem repetir a mesma ideia.
- Cada item precisa se entender sozinho: não cite o material ("segundo o slide 3", "no texto acima").
- Nível de prova de graduação: cobre entendimento, não só decoreba.
- Múltipla escolha: exatamente 4 alternativas, uma só correta, as erradas plausíveis; varie a posição da certa.
  Não use "todas as anteriores" nem "nenhuma das anteriores".
- Verdadeiro ou falso: uma afirmação sem ambiguidade; misture verdadeiras e falsas. Em "resposta", só "V" ou "F".
- Aberta: em "resposta", a resposta esperada em 1 a 3 frases.
- "explicacao": 1 ou 2 frases dizendo por que a resposta está certa.
- Flashcards: na frente, uma pergunta ou conceito; no verso, a resposta curta e direta (uma ideia por cartão).
  Não copie as questões nos flashcards.
- Não use quebras de linha dentro dos campos.
- Gere exatamente as quantidades pedidas. Se a quantidade de algo for 0, devolva a lista vazia."""


def montar_pedido(disciplina, topico, quantidade_questoes, tipos, quantidade_flashcards, pedido_extra):
    """O texto do pedido (vai junto com o material)."""
    linhas = [f'Disciplina: {disciplina}.']
    if topico:
        linhas.append(f'Tópico: {topico}.')
    if quantidade_questoes:
        nomes = ', '.join(TIPOS[t] for t in tipos)
        linhas.append(f'Gere {quantidade_questoes} questões, distribuídas entre estes tipos: {nomes}.')
    else:
        linhas.append('Não gere questões (lista vazia).')
    if quantidade_flashcards:
        linhas.append(f'Gere {quantidade_flashcards} flashcards.')
    else:
        linhas.append('Não gere flashcards (lista vazia).')
    if pedido_extra:
        linhas.append(f'Pedido extra da estudante: {pedido_extra}')
    return '\n'.join(linhas)


def conteudo_do_material(pdf=None, texto=''):
    """O material no formato da API: o PDF vai inteiro (o Claude lê texto e imagens dos slides)."""
    if pdf is not None:
        return {'type': 'document',
                'source': {'type': 'base64', 'media_type': 'application/pdf',
                           'data': base64.standard_b64encode(pdf).decode('ascii')}}
    return {'type': 'text', 'text': f'<material>\n{texto}\n</material>'}


def modo():
    """'assinatura' ou 'api', conforme o IA_MODO do .env."""
    return 'api' if os.environ.get('IA_MODO', '').strip().lower() == 'api' else 'assinatura'


def pedir_ao_claude(material, pedido, sistema=SISTEMA, esquema=ESQUEMA, max_tokens=MAX_TOKENS):
    """O pedido ao Claude (separado para os testes poderem trocá-lo por uma resposta falsa).
    material: o bloco de conteudo_do_material. esquema=None: resposta em texto livre (o guia em HTML)."""
    if modo() == 'api':
        return pedir_pela_api(material, pedido, sistema, esquema, max_tokens)
    if material.get('type') == 'document':
        pdf, texto = base64.standard_b64decode(material['source']['data']), ''
    else:
        pdf, texto = None, material.get('text', '')
    try:
        return assinatura.pedir(pdf=pdf, texto=texto, pedido=pedido, sistema=sistema, esquema=esquema,
                                max_tokens=max_tokens, modelo=MODELO)
    except assinatura.ErroDaAssinatura as erro:
        raise ErroDaIA(str(erro))


def pedir_pela_api(material, pedido, sistema, esquema, max_tokens):
    """A chamada à API. Usa "stream" porque a resposta pode demorar; no fim pegamos a mensagem inteira."""
    formato = {'effort': 'medium'}
    if esquema:
        formato['format'] = {'type': 'json_schema', 'schema': esquema}
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise ErroDaIA('Falta a chave da API: coloque ANTHROPIC_API_KEY no arquivo .env e reinicie o servidor.')
    cliente = anthropic.Anthropic()
    try:
        with cliente.beta.messages.stream(
            model=MODELO,
            max_tokens=max_tokens,
            system=sistema,
            messages=[{'role': 'user', 'content': [material, {'type': 'text', 'text': pedido}]}],
            output_config=formato,
            # Se o Opus recusar (filtro de segurança), a própria API tenta outro modelo recomendado
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
        ) as stream:
            return stream.get_final_message()
    except anthropic.AuthenticationError:
        raise ErroDaIA('A chave da API não foi aceita. Confira o ANTHROPIC_API_KEY no arquivo .env.')
    except anthropic.PermissionDeniedError:
        raise ErroDaIA('A conta da API não tem permissão (os créditos podem ter acabado). Confira em platform.claude.com.')
    except anthropic.RateLimitError:
        raise ErroDaIA('Muitos pedidos seguidos. Espere um minuto e tente de novo.')
    except anthropic.BadRequestError as erro:
        texto = str(getattr(erro, 'message', erro))
        if 'credit' in texto.lower():
            raise ErroDaIA('Os créditos da API acabaram. Compre mais em platform.claude.com (Billing).')
        raise ErroDaIA(f'A API recusou o pedido: {texto[:200]}')
    except anthropic.APIConnectionError:
        raise ErroDaIA('Não consegui falar com a API. Confira a internet e tente de novo.')
    except anthropic.APIStatusError as erro:
        raise ErroDaIA(f'A API deu erro ({erro.status_code}). Tente de novo daqui a pouco.')


def calcular_custo(modelo, tokens_entrada, tokens_saida):
    entrada, saida = PRECOS.get(modelo, PRECOS[MODELO])
    return (entrada * tokens_entrada + saida * tokens_saida) / Decimal(1_000_000)


def ler_resposta(mensagem):
    """(dados, erro): o JSON da resposta, ou o motivo de não ter dado certo."""
    if mensagem.stop_reason == 'refusal':
        return None, 'O Claude recusou gerar a partir desse material.'
    if mensagem.stop_reason == 'max_tokens':
        return None, 'A resposta ficou grande demais e foi cortada. Peça menos itens de uma vez.'
    texto = next((bloco.text for bloco in mensagem.content if bloco.type == 'text'), '')
    try:
        return json.loads(texto), None
    except json.JSONDecodeError:
        return None, 'A resposta veio num formato inesperado. Tente de novo.'


# ===== JSON -> texto da importação =====

def uma_linha(texto):
    """Junta as linhas: na importação, uma linha nova pode ser confundida com um campo novo."""
    return ' '.join(str(texto).split())


def proteger(texto, padroes):
    """Se o texto começar como um marcador (ex.: "R: ..." ou "A) ..."), põe um "· " na frente
    para o leitor da importação não achar que é um campo novo."""
    texto = uma_linha(texto)
    return f'· {texto}' if any(p.match(texto) for p in padroes) else texto


def questoes_em_texto(questoes):
    marcadores = (MARCADOR_QUESTAO, ALTERNATIVA)
    blocos = []
    for q in questoes:
        enunciado = proteger(q.get('enunciado', ''), marcadores)
        explicacao = proteger(q.get('explicacao', ''), marcadores)
        tipo = q.get('tipo')
        if tipo == 'multipla':
            linhas = [f'P: {enunciado}']
            for i, alternativa in enumerate(q.get('alternativas', [])[:8]):
                texto = uma_linha(alternativa.get('texto', ''))
                texto = MARCA_DE_CERTA.sub('', texto)  # um "*" no fim seria lido como "esta é a certa"
                certa = ' *' if alternativa.get('correta') else ''
                linhas.append(f'{chr(65 + i)}) {texto}{certa}')
        elif tipo == 'vf':
            linhas = [f'P: [V/F] {enunciado}', f'R: {uma_linha(q.get("resposta", ""))[:1].upper()}']
        else:
            linhas = [f'P: [aberta] {enunciado}', f'R: {proteger(q.get("resposta", ""), marcadores)}']
        if explicacao:
            linhas.append(f'E: {explicacao}')
        blocos.append('\n'.join(linhas))
    return '\n\n'.join(blocos)


def flashcards_em_texto(cartoes):
    blocos = []
    for c in cartoes:
        frente = proteger(c.get('frente', ''), (MARCADOR_CARTAO,))
        verso = proteger(c.get('verso', ''), (MARCADOR_CARTAO,))
        blocos.append(f'F: {frente}\nV: {verso}')
    return '\n\n'.join(blocos)


def uso_e_custo(mensagem):
    """Pela assinatura não há custo em dólar (sai do limite do plano): o custo fica 0."""
    uso = mensagem.usage
    via = getattr(mensagem, 'via', 'api')
    return {
        'via': via,
        'modelo': mensagem.model,
        'tokens_entrada': uso.input_tokens,
        'tokens_saida': uso.output_tokens,
        'custo': Decimal('0') if via == 'assinatura' else calcular_custo(mensagem.model, uso.input_tokens, uso.output_tokens),
    }


def gerar(*, disciplina, topico, quantidade_questoes, tipos, quantidade_flashcards, pedido_extra,
          pdf=None, texto=''):
    """Faz o pedido e devolve um dicionário com os campos para guardar numa Geracao.
    Levanta ErroDaIA se nem chegou a ter resposta (sem custo)."""
    pedido = montar_pedido(disciplina, topico, quantidade_questoes, tipos, quantidade_flashcards, pedido_extra)
    mensagem = pedir_ao_claude(conteudo_do_material(pdf=pdf, texto=texto), pedido)

    resultado = {
        **uso_e_custo(mensagem),
        'texto_questoes': '',
        'texto_flashcards': '',
        'erro': '',
    }
    dados, erro = ler_resposta(mensagem)
    if erro:
        resultado['erro'] = erro
        return resultado
    resultado['texto_questoes'] = questoes_em_texto(dados.get('questoes', []))
    resultado['texto_flashcards'] = flashcards_em_texto(dados.get('flashcards', []))
    return resultado


PDF_MAXIMO = 20 * 1024 * 1024  # 20 MB (a API aceita 32 MB por pedido, e o PDF cresce ~33% ao ser enviado)
TEXTO_MAXIMO = 300_000  # caracteres


def eh_pdf(conteudo):
    return conteudo[:5] == b'%PDF-'



# ===== Resumo no caderno: um guia de estudo em HTML (vira uma página de material) =====

MAX_TOKENS_RESUMO = 64000  # um guia completo pode passar de 30 mil tokens

SISTEMA_RESUMO = """Você transforma material de aula (slides ou texto) em um guia de estudo em HTML para uma \
estudante brasileira de Ciência da Computação. O guia abre dentro do caderno digital dela, numa caixa isolada.

Responda SOMENTE com o documento HTML completo, começando em <!DOCTYPE html> e terminando em </html>.
Nada antes nem depois (sem cercas de código e sem comentários fora do HTML).

Conteúdo:
- Português do Brasil, linguagem simples e direta, sem enrolação. Baseie-se no material enviado.
- <title> com um nome curto do assunto (ele vira o título da página no caderno).
- Uma seção por tópico/aula, cada uma com: a ideia central em 1 ou 2 frases, a explicação,
  tabelas quando ajudarem a comparar, e um "Teste-se" com perguntas cuja resposta fica escondida
  em <details><summary>.
- Não cite o material ("no slide 4"): o guia deve se entender sozinho.

Visual e código:
- Um arquivo só: CSS e JavaScript dentro do próprio HTML. Pode usar fontes do Google Fonts;
  nenhuma outra biblioteca externa, nenhuma requisição de rede (fetch) e nenhum formulário.
- Estilo: fundo escuro (#1a1216 a #241820), texto claro, destaques em rosa (#e0609a) e lilás (#a77bf3),
  cantos arredondados; títulos em "Bricolage Grotesque", texto em "Figtree", rótulos e números em "JetBrains Mono".
- Topo com o título, uma frase sobre o conteúdo e "chips" com os tópicos.
- Índice lateral fixo com links para as seções; em tela estreita (menos de 900px), o índice vai para o topo.
- Ao lado de cada item do índice, uma bolinha "estudado" que a estudante marca com um clique; guarde isso no
  localStorage (chave começando com "guia-") e marque de novo ao abrir.
- Tabelas legíveis no fundo escuro, contraste bom, nada de texto minúsculo."""

DETALHES = {
    'curto': ('Faça um resumo ENXUTO: só as ideias centrais de cada tópico, no máximo uma tabela por seção '
              'e 2 perguntas no "Teste-se" de cada seção.'),
    'completo': ('Faça um guia COMPLETO: todos os tópicos do material, com exemplos resolvidos passo a passo '
                 'quando houver contas ou procedimentos, uma caixa de "pegadinhas" (o que costuma confundir), '
                 '3 a 5 perguntas no "Teste-se" de cada seção e, no fim, uma seção "para decorar" com termos, '
                 'números e siglas importantes.'),
}


def montar_pedido_resumo(disciplina, topico, detalhe, pedido_extra):
    linhas = []
    if disciplina:
        linhas.append(f'Disciplina: {disciplina}.')
    if topico:
        linhas.append(f'Tópico: {topico}.')
    linhas.append(DETALHES[detalhe])
    if pedido_extra:
        linhas.append(f'Pedido extra da estudante: {pedido_extra}')
    return '\n'.join(linhas)


def extrair_html(mensagem):
    """(html, erro): o documento HTML da resposta, ou o motivo de não ter dado certo."""
    if mensagem.stop_reason == 'refusal':
        return None, 'O Claude recusou gerar a partir desse material.'
    if mensagem.stop_reason == 'max_tokens':
        return None, 'O guia ficou grande demais e foi cortado. Tente o resumo curto ou envie menos slides.'
    texto = ''.join(bloco.text for bloco in mensagem.content if bloco.type == 'text')
    inicio = re.search(r'<!doctype html|<html', texto, re.IGNORECASE)
    fim = texto.lower().rfind('</html>')
    if not inicio or fim == -1:
        return None, 'A resposta não veio como um HTML completo. Tente de novo.'
    return texto[inicio.start():fim + len('</html>')], None


def gerar_resumo(*, disciplina, topico, detalhe, pedido_extra, pdf=None, texto=''):
    """Pede o guia em HTML. Devolve os campos para a Geracao + 'html' (None se não deu certo)."""
    pedido = montar_pedido_resumo(disciplina, topico, detalhe, pedido_extra)
    mensagem = pedir_ao_claude(conteudo_do_material(pdf=pdf, texto=texto), pedido,
                               sistema=SISTEMA_RESUMO, esquema=None, max_tokens=MAX_TOKENS_RESUMO)
    html, erro = extrair_html(mensagem)
    return {**uso_e_custo(mensagem), 'erro': erro or '', 'html': html}


# ===== Texto de uma página do caderno (para gerar questões a partir dela) =====

class _LeitorDeTexto(HTMLParser):
    """Junta só o texto visível de um HTML (pula <script> e <style>)."""

    def __init__(self):
        super().__init__()
        self.partes, self.pular = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.pular += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.pular:
            self.pular -= 1

    def handle_data(self, data):
        if not self.pular and data.strip():
            self.partes.append(data.strip())


def texto_da_pagina(pagina):
    """O texto de uma página: na escrita, o que ela escreveu; no material, o guia + as anotações."""
    partes = []
    if pagina.material:
        leitor = _LeitorDeTexto()
        leitor.feed(pagina.html)
        partes.append('\n'.join(leitor.partes))
    if pagina.texto.strip():
        partes.append(('Anotações da estudante:\n' if pagina.material else '') + pagina.texto.strip())
    return '\n\n'.join(partes)[:TEXTO_MAXIMO]
