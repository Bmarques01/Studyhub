"""Lê questões coladas em texto (por exemplo, geradas pelo Claude), no formato:

    P: Qual protocolo de transporte o BGP usa?
    A) UDP
    B) TCP *
    C) ICMP
    E: O BGP usa TCP na porta 179 para ter entrega confiável.

    P: [V/F] O BGP é um protocolo de roteamento interno (IGP).
    R: F
    E: O BGP é um EGP, usado entre sistemas autônomos.

    P: [aberta] Explique a diferença entre IGP e EGP.
    R: IGP roteia dentro de um sistema autônomo; EGP, entre sistemas autônomos.

Regras:
- Cada "P:" começa uma questão nova; linhas seguintes continuam o campo de cima.
- Múltipla escolha: alternativas "A)" ou "A." e a certa marcada com * no fim (ou "R: B").
- V/F: "R: V" ou "R: F" (também aceita "verdadeiro"/"falso"). Aberta: "R:" com a resposta esperada.
- "E:" (explicação) é opcional. Numeração ("1. P:"), títulos "#" e linhas "---" são ignorados.
"""
import re

LIMITE = 300  # questões por vez
MAX_ALTERNATIVAS = 8

MARCADOR = re.compile(
    r'^\s*(?:\d+\s*[.)-]\s*)?(p|pergunta|r|resposta|e|explica[cç][aã]o)\s*:\s?(.*)$', re.IGNORECASE)
ALTERNATIVA = re.compile(r'^\s*([a-h])\s*[).]\s+(.*?)\s*$', re.IGNORECASE)
MARCA_DE_CERTA = re.compile(r'\s*(\*|✓|✔|\(x\)|\[x\]|\(correta\))\s*$', re.IGNORECASE)
ETIQUETA = re.compile(r'^\s*\[\s*(v\s*/?\s*f|aberta|m[uú]ltipla)\s*\]\s*', re.IGNORECASE)
IGNORAR = re.compile(r'^\s*(#.*|[-=*_]{3,})\s*$')  # títulos e linhas separadoras de markdown

VERDADEIRO = {'v', 'verdadeiro', 'verdadeira', 'true', 'certo', 'correto'}
FALSO = {'f', 'falso', 'falsa', 'false', 'errado', 'incorreto'}


def ler_vf(texto):
    """'V', 'F' ou None, a partir de 'R: Verdadeiro.', 'R: f', etc."""
    palavra = texto.strip().strip('.!').lower()
    if palavra in VERDADEIRO:
        return 'V'
    if palavra in FALSO:
        return 'F'
    return None


def montar(bloco):
    """Transforma um bloco lido em questão. Devolve (questao, None) ou (None, motivo do problema)."""
    enunciado = '\n'.join(bloco['enunciado']).strip()
    etiqueta = None
    achada = ETIQUETA.match(enunciado)
    if achada:
        etiqueta = achada.group(1).lower().replace(' ', '').replace('/', '')  # "vf", "aberta", "multipla"
        etiqueta = 'multipla' if etiqueta.startswith('m') else etiqueta
        enunciado = enunciado[achada.end():].strip()
    if not enunciado:
        return None, 'sem enunciado (P:)'

    resposta = '\n'.join(bloco['resposta']).strip()
    explicacao = '\n'.join(bloco['explicacao']).strip()
    questao = {'enunciado': enunciado, 'explicacao': explicacao, 'alternativas': [], 'resposta': ''}

    alternativas = bloco['alternativas']
    if alternativas:
        if len(alternativas) < 2:
            return None, 'precisa de pelo menos 2 alternativas'
        if len(alternativas) > MAX_ALTERNATIVAS:
            return None, f'no máximo {MAX_ALTERNATIVAS} alternativas'
        textos, certas = [], []
        for i, linhas in enumerate(alternativas):
            texto = '\n'.join(linhas).strip()
            marca = MARCA_DE_CERTA.search(texto)
            if marca:
                texto = texto[:marca.start()].strip()
                certas.append(i)
            if not texto:
                return None, f'alternativa {chr(65 + i)} vazia'
            textos.append(texto)
        letra = resposta.strip(' .)').upper()
        if not certas and len(letra) == 1 and 'A' <= letra < chr(65 + len(textos)):
            certas = [ord(letra) - 65]  # "R: B"
        if not certas:
            return None, 'nenhuma alternativa certa (marque com * no fim)'
        if len(certas) > 1:
            return None, 'mais de uma alternativa marcada como certa'
        questao['tipo'] = 'multipla'
        questao['alternativas'] = [(texto, i == certas[0]) for i, texto in enumerate(textos)]
        return questao, None

    if etiqueta == 'multipla':
        return None, 'múltipla escolha sem alternativas (A), B)...)'
    if etiqueta == 'vf' or (etiqueta is None and ler_vf(resposta)):
        valor = ler_vf(resposta)
        if not valor:
            return None, 'V/F sem a resposta (R: V ou R: F)'
        questao.update(tipo='vf', resposta=valor)
        return questao, None
    if not resposta:
        return None, 'sem resposta (R:)'
    questao.update(tipo='aberta', resposta=resposta)
    return questao, None


def ler_questoes(texto):
    """Devolve (questoes, problemas).
    questoes = [{'tipo', 'enunciado', 'alternativas': [(texto, correta)], 'resposta', 'explicacao'}]
    problemas = [(começo do enunciado, motivo)]"""
    questoes, problemas = [], []
    bloco = None   # {'enunciado': [], 'alternativas': [[linhas], ...], 'resposta': [], 'explicacao': []}
    campo = None   # onde entram as próximas linhas: 'enunciado', 'alternativa', 'resposta', 'explicacao'

    def fechar():
        if bloco is None:
            return
        questao, motivo = montar(bloco)
        if questao:
            questoes.append(questao)
        else:
            inicio = ' '.join(' '.join(bloco['enunciado']).split())[:60] or '(sem enunciado)'
            problemas.append((inicio, motivo))

    for linha in texto.splitlines():
        if IGNORAR.match(linha):
            continue
        marcador = MARCADOR.match(linha)
        if marcador:
            tipo, resto = marcador.group(1)[0].lower(), marcador.group(2)
            if tipo == 'p':
                fechar()
                bloco = {'enunciado': [resto], 'alternativas': [], 'resposta': [], 'explicacao': []}
                campo = 'enunciado'
            elif bloco is not None:
                campo = 'resposta' if tipo == 'r' else 'explicacao'
                bloco[campo].append(resto)
            continue
        if bloco is None:
            continue  # texto antes da primeira questão (ex.: "Aqui estão as questões:")
        alternativa = ALTERNATIVA.match(linha)
        if alternativa and campo in ('enunciado', 'alternativa'):
            bloco['alternativas'].append([alternativa.group(2)])
            campo = 'alternativa'
        elif campo == 'alternativa':
            if linha.strip():
                bloco['alternativas'][-1].append(linha)
        else:
            bloco[campo].append(linha)

    fechar()
    return questoes, problemas
