"""Conversa com o Claude (API da Anthropic) para gerar questões e flashcards a partir de um material.

Como funciona:
1. Montamos o pedido: o material (PDF dos slides ou texto) + o que gerar.
2. Pedimos a resposta num formato fixo (JSON com um "esquema"): assim ela sempre vem
   organizada, com o tipo de cada questão, as alternativas, a certa etc.
3. Transformamos esse JSON no MESMO texto da importação (P: / A) ... * / R: / E: e F: / V:).
   Assim a revisão usa os leitores que já existem, e a Bruna pode editar o texto antes de salvar.

A chave da API vem do arquivo .env (ANTHROPIC_API_KEY) e nunca vai para o navegador.
"""
import base64
import json
import os
from decimal import Decimal

import anthropic

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


def pedir_ao_claude(material, pedido):
    """A chamada à API (separada para os testes poderem trocá-la por uma resposta falsa).
    Usa "stream" porque a resposta pode demorar; no fim pegamos a mensagem inteira."""
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise ErroDaIA('Falta a chave da API: coloque ANTHROPIC_API_KEY no arquivo .env e reinicie o servidor.')
    cliente = anthropic.Anthropic()
    try:
        with cliente.beta.messages.stream(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            system=SISTEMA,
            messages=[{'role': 'user', 'content': [material, {'type': 'text', 'text': pedido}]}],
            output_config={'effort': 'medium', 'format': {'type': 'json_schema', 'schema': ESQUEMA}},
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


def gerar(*, disciplina, topico, quantidade_questoes, tipos, quantidade_flashcards, pedido_extra,
          pdf=None, texto=''):
    """Faz o pedido e devolve um dicionário com os campos para guardar numa Geracao.
    Levanta ErroDaIA se nem chegou a ter resposta (sem custo)."""
    pedido = montar_pedido(disciplina, topico, quantidade_questoes, tipos, quantidade_flashcards, pedido_extra)
    mensagem = pedir_ao_claude(conteudo_do_material(pdf=pdf, texto=texto), pedido)

    uso = mensagem.usage
    resultado = {
        'modelo': mensagem.model,
        'tokens_entrada': uso.input_tokens,
        'tokens_saida': uso.output_tokens,
        'custo': calcular_custo(mensagem.model, uso.input_tokens, uso.output_tokens),
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

