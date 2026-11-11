"""Onde melhorar: quais disciplinas e tópicos estão mais fracos, pelos questionários e flashcards.

A ideia:
- Questões: das últimas JANELA respostas de cada tópico, quantas ela acertou.
- Flashcards: das últimas JANELA revisões de cada tópico, quantas ela lembrou
  (qualquer nota menos "errei", igual o FSRS considera).
- O "domínio" do tópico é a média dessas duas porcentagens (ou só a que existir).
- A setinha compara a janela recente com a janela anterior (as JANELA respostas antes dela).

Só conta o que é recente: se ela estudou e melhorou, o tópico sai da lista dos fracos.
"""
from collections import defaultdict

from estudos.models import Disciplina, Topico
from flashcards.models import Flashcard, Revisao
from questoes.models import Erro, Questao, Resposta

JANELA = 20         # quantas respostas recentes contam
MINIMO = 5          # menos que isso = "poucos dados" (uma questão errada não marca o tópico como fraco)
VARIACAO = 10       # pontos de diferença para a setinha aparecer
FRACO = 60          # abaixo disso: "precisa de atenção"
BOM = 80            # a partir disso: "indo bem" (no meio: "quase lá")


def arredondar(numero):
    """Arredondamento da escola (66,5 → 67). O round() do Python faria 66,5 → 66."""
    return int(numero + 0.5)


def porcentagem(lista):
    """lista de True/False → % de True (ou None se não tiver o mínimo)."""
    if len(lista) < MINIMO:
        return None
    return arredondar(sum(lista) / len(lista) * 100)


def resumo_da_parte(resultados):
    """resultados = True/False do mais novo para o mais antigo → % recente, setinha e quantidade."""
    recentes = resultados[:JANELA]
    anteriores = resultados[JANELA:JANELA * 2]
    agora, antes = porcentagem(recentes), porcentagem(anteriores)
    tendencia = ''
    if agora is not None and antes is not None:
        if agora - antes >= VARIACAO:
            tendencia = 'subiu'
        elif antes - agora >= VARIACAO:
            tendencia = 'caiu'
    return {'pct': agora, 'tendencia': tendencia, 'quantidade': len(recentes), 'recentes': recentes}


def situacao(dominio):
    if dominio is None:
        return {'chave': 'poucos', 'texto': 'poucos dados', 'simbolo': '…'}
    if dominio < FRACO:
        return {'chave': 'fraco', 'texto': 'precisa de atenção', 'simbolo': '!'}
    if dominio < BOM:
        return {'chave': 'quase', 'texto': 'quase lá', 'simbolo': '~'}
    return {'chave': 'bem', 'texto': 'indo bem', 'simbolo': '✓'}


def montar_linha(questoes, flashcards):
    """Junta as duas partes de um tópico (ou de uma disciplina inteira)."""
    partes = [p['pct'] for p in (questoes, flashcards) if p['pct'] is not None]
    dominio = arredondar(sum(partes) / len(partes)) if partes else None
    return {'questoes': questoes, 'flashcards': flashcards, 'dominio': dominio, 'situacao': situacao(dominio)}


def ordem(linha):
    """Mais fraco primeiro; os com poucos dados vão para o fim."""
    return (linha['dominio'] is None, linha['dominio'] or 0)


def pontos_fracos():
    """Lista de disciplinas (mais fraca primeiro), cada uma com seus tópicos (mais fraco primeiro).
    Só entram disciplinas e tópicos que já têm alguma resposta ou revisão."""
    # chave = (disciplina_id, topico_id ou None) → True/False, do mais novo para o mais antigo
    acertos = defaultdict(list)
    for d, t, acertou in (Resposta.objects.order_by('-respondida_em', '-id')
                          .values_list('questao__disciplina_id', 'questao__topico_id', 'acertou')):
        acertos[(d, t)].append(acertou)

    lembrou = defaultdict(list)
    for d, t, nota in (Revisao.objects.order_by('-revisada_em', '-id')
                       .values_list('flashcard__disciplina_id', 'flashcard__topico_id', 'nota')):
        lembrou[(d, t)].append(nota > 1)  # 1 = "errei"

    chaves = set(acertos) | set(lembrou)
    if not chaves:
        return []

    # o que existe em cada tópico, para mostrar só os botões que fazem sentido
    tem_questoes = set(Questao.objects.values_list('disciplina_id', 'topico_id'))
    tem_cartoes = set(Flashcard.objects.values_list('disciplina_id', 'topico_id'))
    erros = defaultdict(int)  # erros ainda no caderno (não dominados)
    for chave in Erro.objects.filter(dominado_em__isnull=True).values_list(
            'questao__disciplina_id', 'questao__topico_id'):
        erros[chave] += 1

    disciplinas = Disciplina.objects.in_bulk({d for d, _ in chaves})
    topicos = Topico.objects.in_bulk({t for _, t in chaves if t})

    por_disciplina = defaultdict(list)
    for chave in chaves:
        d, t = chave
        if d not in disciplinas:
            continue
        linha = montar_linha(resumo_da_parte(acertos[chave]), resumo_da_parte(lembrou[chave]))
        linha.update({
            'topico': topicos.get(t),  # None = as questões/cartões sem tópico
            'tem_questoes': chave in tem_questoes,
            'tem_cartoes': chave in tem_cartoes,
            'erros': erros[chave],
        })
        por_disciplina[d].append(linha)

    resultado = []
    for d, linhas in por_disciplina.items():
        linhas.sort(key=lambda l: (ordem(l), l['topico'].nome if l['topico'] else ''))
        # a disciplina junta as janelas recentes dos tópicos dela
        juntar = lambda parte: [r for l in linhas for r in l[parte]['recentes']]
        q, f = juntar('questoes'), juntar('flashcards')
        geral = montar_linha({'pct': porcentagem(q), 'quantidade': len(q), 'tendencia': ''},
                             {'pct': porcentagem(f), 'quantidade': len(f), 'tendencia': ''})
        geral.update({'disciplina': disciplinas[d], 'topicos': linhas,
                      'erros': sum(l['erros'] for l in linhas)})
        resultado.append(geral)
    resultado.sort(key=lambda g: (ordem(g), g['disciplina'].nome))
    return resultado


def mais_fracos(grupos, limite=3):
    """Os tópicos mais fracos de todas as disciplinas (para o bloco do dashboard), a partir do
    resultado de pontos_fracos(). Só os que estão abaixo de "indo bem"."""
    todos = [dict(t, disciplina=g['disciplina']) for g in grupos for t in g['topicos']
             if t['dominio'] is not None and t['dominio'] < BOM]
    todos.sort(key=ordem)
    return todos[:limite]
