"""Os períodos do filtro do dashboard: esta semana, semana passada, este mês, mês passado.

Cada período sabe as suas datas e as do período anterior (para o gráfico comparar).
Ex.: "mês passado" em 03/11/2026 → 01/10 a 31/10, comparado com 01/09 a 30/09.
"""
from datetime import timedelta

from django.utils.formats import date_format

OPCOES = [
    ('semana', 'esta semana'),
    ('semana_passada', 'semana passada'),
    ('mes', 'este mês'),
    ('mes_passado', 'mês passado'),
]
PADRAO = 'semana'


def inicio_do_mes_anterior(dia):
    return (dia.replace(day=1) - timedelta(days=1)).replace(day=1)


def fim_do_mes(inicio):
    proximo = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)  # dia 28 + 4 sempre cai no mês seguinte
    return proximo - timedelta(days=1)


def nome_do_mes(dia):
    return date_format(dia, 'F').lower()  # "novembro"


def periodo(chave, hoje):
    """Dicionário com tudo que o dashboard precisa saber do período escolhido."""
    if chave not in dict(OPCOES):
        chave = PADRAO

    if chave in ('semana', 'semana_passada'):
        inicio = hoje - timedelta(days=hoje.weekday())  # segunda-feira
        if chave == 'semana_passada':
            inicio -= timedelta(weeks=1)
        fim = inicio + timedelta(days=6)
        anterior_inicio = inicio - timedelta(weeks=1)
        anterior_fim = fim - timedelta(weeks=1)
        rotulos = (('esta semana', 'semana passada') if chave == 'semana'
                   else ('semana passada', 'semana retrasada'))
    else:
        inicio = hoje.replace(day=1)
        if chave == 'mes_passado':
            inicio = inicio_do_mes_anterior(inicio)
        fim = fim_do_mes(inicio)
        anterior_inicio = inicio_do_mes_anterior(inicio)
        anterior_fim = fim_do_mes(anterior_inicio)
        rotulos = (nome_do_mes(inicio), nome_do_mes(anterior_inicio))

    return {
        'chave': chave,
        'nome': dict(OPCOES)[chave],
        'tipo': 'semana' if chave.startswith('semana') else 'mes',
        'inicio': inicio,
        'fim': fim,
        'anterior_inicio': anterior_inicio,
        'anterior_fim': anterior_fim,
        'rotulo_atual': rotulos[0],
        'rotulo_anterior': rotulos[1],
    }
