"""Lê cartões colados em texto, no formato:

    F: Qual porta o BGP usa?
    V: TCP, porta 179.

    F: O que é um AS?
    V: Um conjunto de redes
    sob a mesma administração.

Cada "F:" começa um cartão novo; as linhas seguintes continuam o campo de cima
(a resposta pode ter várias linhas). Também aceita "frente:" e "verso:", maiúsculas ou minúsculas.
"""
import re

MARCADOR = re.compile(r'^\s*(f|v|frente|verso)\s*:\s?(.*)$', re.IGNORECASE)
LIMITE = 500  # cartões por vez


def ler_cartoes(texto):
    """Devolve (cartoes, problemas): cartoes = [(frente, verso)], problemas = textos dos blocos ignorados."""
    cartoes, problemas = [], []
    atual = None   # {'frente': [linhas], 'verso': [linhas] ou None}
    campo = None   # em qual campo as próximas linhas entram

    def fechar():
        if atual is None:
            return
        frente = '\n'.join(atual['frente']).strip()
        verso = '\n'.join(atual['verso'] or []).strip()
        if frente and verso:
            cartoes.append((frente, verso))
        else:
            problemas.append(frente[:50] or verso[:50] or '(vazio)')

    for linha in texto.splitlines():
        marcador = MARCADOR.match(linha)
        if marcador:
            tipo, resto = marcador.group(1)[0].lower(), marcador.group(2)
            if tipo == 'f':
                fechar()
                atual, campo = {'frente': [resto], 'verso': None}, 'frente'
            elif atual is None or atual['verso'] is not None:
                # "V:" sem um "F:" antes (ou um segundo "V:"): vira um bloco com problema
                fechar()
                atual, campo = {'frente': [], 'verso': [resto]}, 'verso'
            else:
                atual['verso'], campo = [resto], 'verso'
        elif atual is not None:
            atual[campo].append(linha)

    fechar()
    return cartoes, problemas
