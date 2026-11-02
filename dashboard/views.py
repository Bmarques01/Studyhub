from datetime import timedelta

from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from calendario.models import Evento
from calendario.views import eventos_por_dia, proximos_eventos, semanas_do_mes
from pomodoro.models import SessaoPomodoro

from .models import Perfil
from .templatetags.tempo import horas

DIAS_SEMANA = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']
SEMANAS_NO_MAPA = 40  # ~9 meses no mapa de calor


# ===== Cálculos =====

def minutos_por_dia(desde):
    """{data: minutos estudados} de 'desde' até hoje, em uma única consulta ao banco."""
    linhas = (SessaoPomodoro.objects
              .filter(concluida_em__date__gte=desde)
              .annotate(dia=TruncDate('concluida_em'))  # data no fuso de São Paulo
              .values('dia')
              .annotate(total=Sum('duracao_minutos')))
    return {linha['dia']: linha['total'] for linha in linhas}


def somar(por_dia, inicio, fim):
    """Soma os minutos entre duas datas (incluindo as duas)."""
    return sum(minutos for dia, minutos in por_dia.items() if inicio <= dia <= fim)


def sequencia_de_dias(por_dia, hoje):
    """Quantos dias seguidos com estudo. Se hoje ainda não estudou, conta a partir de ontem
    (a sequência só "quebra" se o dia acabar sem estudo)."""
    dia = hoje if por_dia.get(hoje) else hoje - timedelta(days=1)
    dias = 0
    while por_dia.get(dia):
        dias += 1
        dia -= timedelta(days=1)
    return dias


def comparacao(atual, anterior):
    """Diferença em relação ao período anterior, pronta para mostrar."""
    diferenca = atual - anterior
    if diferenca == 0:
        return {'texto': '±0', 'direcao': 'igual'}
    return {
        'texto': ('+' if diferenca > 0 else '−') + horas(abs(diferenca)),
        'direcao': 'subiu' if diferenca > 0 else 'desceu',
    }


def escala(maximo):
    """Topo do eixo do gráfico arredondado para horas cheias (mínimo 1h)."""
    return max(60, -(-maximo // 60) * 60)  # -(-a // b) = divisão arredondando para cima


def nivel_do_dia(minutos):
    """Intensidade da cor no mapa de calor (0 = nada, 4 = muito)."""
    if not minutos:
        return 0
    if minutos < 30:
        return 1
    if minutos < 60:
        return 2
    if minutos < 120:
        return 3
    return 4


# ===== Página =====

def index(request):
    agora = timezone.localtime()
    hoje = agora.date()
    perfil = Perfil.atual()

    inicio_semana = hoje - timedelta(days=hoje.weekday())  # segunda-feira
    inicio_mes = hoje.replace(day=1)
    inicio_mes_passado = (inicio_mes - timedelta(days=1)).replace(day=1)
    inicio_mapa = inicio_semana - timedelta(weeks=SEMANAS_NO_MAPA - 1)

    por_dia = minutos_por_dia(min(inicio_mapa, inicio_mes_passado))

    # --- Números do topo ---
    min_hoje = por_dia.get(hoje, 0)
    min_ontem = por_dia.get(hoje - timedelta(days=1), 0)
    min_semana = somar(por_dia, inicio_semana, hoje)
    # semana passada "até o mesmo dia", para a comparação ser justa
    min_semana_passada = somar(por_dia, inicio_semana - timedelta(weeks=1), hoje - timedelta(weeks=1))
    min_mes = somar(por_dia, inicio_mes, hoje)
    ultimo_dia_mes_passado = inicio_mes - timedelta(days=1)
    min_mes_passado = somar(por_dia, inicio_mes_passado,
                            inicio_mes_passado.replace(day=min(hoje.day, ultimo_dia_mes_passado.day)))

    meta_min = perfil.meta_semanal_horas * 60
    meta_pct = round(min_semana / meta_min * 100) if meta_min else 0

    # --- Gráfico: esta semana × semana passada, dia a dia ---
    colunas = []
    for i, nome in enumerate(DIAS_SEMANA):
        dia = inicio_semana + timedelta(days=i)
        colunas.append({
            'nome': nome,
            'data': dia,
            'atual': por_dia.get(dia, 0) if dia <= hoje else None,  # None = dia ainda não chegou
            'anterior': por_dia.get(dia - timedelta(weeks=1), 0),
            'hoje': dia == hoje,
        })
    topo = escala(max([c['atual'] or 0 for c in colunas] + [c['anterior'] for c in colunas]))
    for c in colunas:
        c['altura_atual'] = (c['atual'] or 0) / topo * 100
        c['altura_anterior'] = c['anterior'] / topo * 100
    marcas_eixo = [topo, topo // 2, 0]

    # --- Mapa de calor: uma coluna por semana, uma linha por dia ---
    mapa = []
    for s in range(SEMANAS_NO_MAPA):
        semana = []
        for d in range(7):
            dia = inicio_mapa + timedelta(weeks=s, days=d)
            minutos = por_dia.get(dia, 0)
            semana.append({
                'data': dia,
                'minutos': minutos,
                'nivel': nivel_do_dia(minutos),
                'futuro': dia > hoje,
            })
        mapa.append(semana)

    # --- Tempo por disciplina (este mês) ---
    por_disciplina = list(
        SessaoPomodoro.objects
        .filter(concluida_em__date__gte=inicio_mes)
        .values('disciplina__nome', 'disciplina__cor')
        .annotate(total=Sum('duracao_minutos'))
        .order_by('-total')
    )
    maior = por_disciplina[0]['total'] if por_disciplina else 0
    for linha in por_disciplina:
        linha['largura'] = linha['total'] / maior * 100

    # --- Calendário do mês: dias com estudo + eventos (provas, trabalhos...) ---
    semanas = semanas_do_mes(hoje.year, hoje.month)
    eventos = eventos_por_dia(semanas[0][0], semanas[-1][-1])
    ordem_tipos = [valor for valor, _ in Evento.TIPOS]
    calendario_mes = [
        [{
            'data': dia,
            'fora': dia.month != hoje.month,
            'hoje': dia == hoje,
            'estudou': bool(por_dia.get(dia)),
            # um ponto por tipo de evento no dia, sempre na mesma ordem
            'tipos': sorted({e.tipo for e in eventos.get(dia, [])}, key=ordem_tipos.index),
            'titulos': ', '.join(e.titulo for e in eventos.get(dia, [])),
        } for dia in semana]
        for semana in semanas
    ]

    if agora.hour < 12:
        saudacao = 'Bom dia'
    elif agora.hour < 18:
        saudacao = 'Boa tarde'
    else:
        saudacao = 'Boa noite'

    return render(request, 'dashboard/index.html', {
        'perfil': perfil,
        'saudacao': saudacao,
        'hoje': hoje,
        'sequencia': sequencia_de_dias(por_dia, hoje),
        'cards': [
            {'rotulo': 'hoje', 'minutos': min_hoje, 'comparacao': comparacao(min_hoje, min_ontem),
             'referencia': 'vs ontem'},
            {'rotulo': 'esta semana', 'minutos': min_semana,
             'comparacao': comparacao(min_semana, min_semana_passada), 'referencia': 'vs semana passada'},
            {'rotulo': 'este mês', 'minutos': min_mes, 'comparacao': comparacao(min_mes, min_mes_passado),
             'referencia': 'vs mês passado'},
        ],
        'meta_min': meta_min,
        'min_semana': min_semana,
        'meta_pct': meta_pct,
        'falta_meta': max(0, meta_min - min_semana),
        'colunas': colunas,
        'marcas_eixo': marcas_eixo,
        'total_semana_passada': sum(c['anterior'] for c in colunas),
        'mapa': mapa,
        'dias_semana': DIAS_SEMANA,
        'por_disciplina': por_disciplina,
        'calendario_mes': calendario_mes,
        'proximos': proximos_eventos(limite=5),
    })


@require_POST
def salvar_meta(request):
    perfil = Perfil.atual()
    try:
        horas_meta = int(request.POST.get('meta_semanal_horas', ''))
    except ValueError:
        return redirect('dashboard:index')
    if 1 <= horas_meta <= 100:
        perfil.meta_semanal_horas = horas_meta
        perfil.save()
    return redirect('dashboard:index')
