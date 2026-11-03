from datetime import timedelta

from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from calendario.models import Evento
from calendario.views import eventos_por_dia, proximos_eventos, semanas_do_mes
from flashcards import memoria
from flashcards.models import Flashcard
from pomodoro.models import SessaoPomodoro
from projetos.models import Projeto

from . import periodos
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


def periodo_escolhido(request, hoje):
    """O filtro vem de ?periodo=...; a escolha fica guardada na sessão para a próxima visita."""
    chave = request.GET.get('periodo')
    if chave in dict(periodos.OPCOES):
        request.session['dashboard_periodo'] = chave
    else:
        chave = request.session.get('dashboard_periodo', periodos.PADRAO)
    return periodos.periodo(chave, hoje)


def grafico(por_dia, periodo, hoje):
    """Colunas do gráfico: período escolhido × período anterior.
    Semana: uma coluna por dia da semana. Mês: uma coluna por dia do mês (dia 1 com dia 1)."""
    colunas = []
    if periodo['tipo'] == 'semana':
        for i, nome in enumerate(DIAS_SEMANA):
            dia = periodo['inicio'] + timedelta(days=i)
            colunas.append({'nome': nome, 'data': dia, 'anterior_data': dia - timedelta(weeks=1)})
    else:
        tamanho_anterior = (periodo['anterior_fim'] - periodo['anterior_inicio']).days + 1
        for i in range((periodo['fim'] - periodo['inicio']).days + 1):
            dia = periodo['inicio'] + timedelta(days=i)
            colunas.append({
                'nome': str(dia.day),
                'data': dia,
                # outubro tem 31 dias e setembro 30: o dia 31 não tem com quem comparar
                'anterior_data': periodo['anterior_inicio'] + timedelta(days=i) if i < tamanho_anterior else None,
                'marca': dia.day in (1, 5, 10, 15, 20, 25, 30),  # só alguns números embaixo, para não embolar
            })

    for c in colunas:
        c['atual'] = por_dia.get(c['data'], 0) if c['data'] <= hoje else None  # None = ainda não chegou
        c['anterior'] = por_dia.get(c['anterior_data'], 0) if c['anterior_data'] else None
        c['hoje'] = c['data'] == hoje
    topo = escala(max([c['atual'] or 0 for c in colunas] + [c['anterior'] or 0 for c in colunas]))
    for c in colunas:
        c['altura_atual'] = (c['atual'] or 0) / topo * 100
        c['altura_anterior'] = (c['anterior'] or 0) / topo * 100
    return colunas, [topo, topo // 2, 0]


MAX_FEITAS = 5  # funcionalidades "feitas no período" mostradas por projeto


def resumo_dos_projetos(periodo, hoje):
    """Um resumo por projeto ativo: progresso, o que está fazendo, o que terminou no período,
    tempo de pomodoro no período e a última entrada do diário."""
    inicio, fim = periodo['inicio'], periodo['fim']
    resumos = []
    for projeto in Projeto.objects.filter(status='ativo').order_by('criado_em'):
        funcionalidades = projeto.funcionalidades.all()
        total = funcionalidades.count()
        feitas_total = funcionalidades.filter(status='feito').count()
        feitas = list(funcionalidades.filter(status='feito', concluida_em__date__gte=inicio,
                                             concluida_em__date__lte=fim).order_by('-concluida_em'))
        minutos = (SessaoPomodoro.objects
                   .filter(projeto=projeto, concluida_em__date__gte=inicio, concluida_em__date__lte=fim)
                   .aggregate(total=Sum('duracao_minutos'))['total'] or 0)
        diario = projeto.diario.order_by('-data', '-criada_em').first()
        resumos.append({
            'projeto': projeto,
            'total': total,
            'feitas_total': feitas_total,
            'porcentagem': round(feitas_total / total * 100) if total else 0,
            'fazendo': list(funcionalidades.filter(status='fazendo').order_by('ordem', 'id')[:3]),
            'feitas': feitas[:MAX_FEITAS],
            'feitas_quantidade': len(feitas),
            'feitas_resto': max(0, len(feitas) - MAX_FEITAS),
            'minutos': minutos,
            'diario': diario,
            'diario_dias': (hoje - diario.data).days if diario else None,
        })
    return resumos


# ===== Página =====

def index(request):
    agora = timezone.localtime()
    hoje = agora.date()
    perfil = Perfil.atual()

    inicio_semana = hoje - timedelta(days=hoje.weekday())  # segunda-feira
    inicio_mes = hoje.replace(day=1)
    inicio_mes_passado = (inicio_mes - timedelta(days=1)).replace(day=1)
    inicio_mapa = inicio_semana - timedelta(weeks=SEMANAS_NO_MAPA - 1)
    periodo = periodo_escolhido(request, hoje)  # o filtro: esta semana, semana passada...

    por_dia = minutos_por_dia(min(inicio_mapa, inicio_mes_passado, periodo['anterior_inicio']))

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

    # --- Gráfico: período escolhido × período anterior (segue o filtro) ---
    colunas, marcas_eixo = grafico(por_dia, periodo, hoje)

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

    # --- Tempo por disciplina e projeto (segue o filtro) ---
    por_disciplina = list(
        SessaoPomodoro.objects
        .filter(concluida_em__date__gte=periodo['inicio'], concluida_em__date__lte=periodo['fim'])
        .values('disciplina__nome', 'disciplina__cor', 'projeto__nome', 'projeto__cor')
        .annotate(total=Sum('duracao_minutos'))
        .order_by('-total')
    )
    maior = por_disciplina[0]['total'] if por_disciplina else 0
    for linha in por_disciplina:
        linha['largura'] = linha['total'] / maior * 100

    # --- Calendário: o mês do período (segue o filtro), com estudo + eventos ---
    # Na semana, o mês de referência é o do último dia que já passou (a semana pode virar o mês)
    mes_referencia = periodo['inicio'] if periodo['tipo'] == 'mes' else min(periodo['fim'], hoje)
    semanas = semanas_do_mes(mes_referencia.year, mes_referencia.month)
    eventos = eventos_por_dia(semanas[0][0], semanas[-1][-1])
    ordem_tipos = [valor for valor, _ in Evento.TIPOS]
    calendario_mes = [
        [{
            'data': dia,
            'fora': dia.month != mes_referencia.month,
            'hoje': dia == hoje,
            # filtro de semana: os dias da semana escolhida ficam destacados
            'no_periodo': periodo['tipo'] == 'semana' and periodo['inicio'] <= dia <= periodo['fim'],
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
        'mapa': mapa,
        'dias_semana': DIAS_SEMANA,
        'por_disciplina': por_disciplina,
        'calendario_mes': calendario_mes,
        'proximos': proximos_eventos(limite=5),
        'periodo': periodo,
        'opcoes_periodo': periodos.OPCOES,
        'mes_referencia': mes_referencia,
        'projetos': resumo_dos_projetos(periodo, hoje),
        'tem_flashcards': Flashcard.objects.exists(),
        'flashcards_hoje': memoria.para_revisar(),
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
