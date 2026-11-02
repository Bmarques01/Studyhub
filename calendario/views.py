import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from estudos.views import avisar_erros, opcoes_de_disciplina

from .forms import EventoForm
from .models import Evento

DIAS_SEMANA = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']


# ===== Funções de apoio (também usadas pelo dashboard) =====

def semanas_do_mes(ano, mes):
    """Semanas do mês (começando na segunda), com os dias de borda dos meses vizinhos."""
    return calendar.Calendar(firstweekday=0).monthdatescalendar(ano, mes)


def eventos_por_dia(inicio, fim):
    """{data: [eventos]} entre duas datas."""
    por_dia = defaultdict(list)
    for evento in Evento.objects.filter(data__range=(inicio, fim)).select_related('disciplina'):
        por_dia[evento.data].append(evento)
    return por_dia


def proximos_eventos(limite=8):
    """Eventos pendentes de hoje em diante."""
    hoje = timezone.localdate()
    return (Evento.objects.filter(data__gte=hoje, concluido=False)
            .select_related('disciplina')[:limite])


def ler_mes(texto):
    """'2026-11' → date(2026, 11, 1). Se vier vazio ou inválido, usa o mês atual."""
    try:
        ano, mes = map(int, (texto or '').split('-'))
        return date(ano, mes, 1)
    except ValueError:
        return timezone.localdate().replace(day=1)


def voltar(request, padrao):
    """Volta para a página de onde veio (campo 'proximo'), se for um endereço do próprio site."""
    destino = request.POST.get('proximo') or request.GET.get('proximo')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(padrao)


def url_do_mes(dia):
    return f"{reverse('calendario:index')}?mes={dia:%Y-%m}"


# ===== Páginas =====

def index(request):
    hoje = timezone.localdate()
    primeiro = ler_mes(request.GET.get('mes'))
    semanas = semanas_do_mes(primeiro.year, primeiro.month)
    por_dia = eventos_por_dia(semanas[0][0], semanas[-1][-1])

    mes_anterior = (primeiro - timedelta(days=1)).replace(day=1)
    proximo_mes = (primeiro + timedelta(days=32)).replace(day=1)

    # Monta a grade: cada dia com seus eventos
    grade = [
        [{'data': dia, 'eventos': por_dia.get(dia, []), 'fora': dia.month != primeiro.month,
          'hoje': dia == hoje} for dia in semana]
        for semana in semanas
    ]

    # Data que já vem preenchida no formulário: hoje, ou o 1º dia do mês que está sendo visto
    data_inicial = hoje if (hoje.year, hoje.month) == (primeiro.year, primeiro.month) else primeiro

    return render(request, 'calendario/index.html', {
        'primeiro': primeiro,
        'grade': grade,
        'dias_semana': DIAS_SEMANA,
        'mes_anterior': mes_anterior,
        'proximo_mes': proximo_mes,
        'eh_mes_atual': (hoje.year, hoje.month) == (primeiro.year, primeiro.month),
        'proximos': proximos_eventos(),
        'tipos': Evento.TIPOS,
        'opcoes': opcoes_de_disciplina(),
        'data_inicial': data_inicial,
    })


@require_POST
def criar(request):
    form = EventoForm(request.POST)
    if form.is_valid():
        evento = form.save()
        messages.success(request, f'"{evento.titulo}" adicionado em {evento.data:%d/%m}.')
        return redirect(url_do_mes(evento.data))
    avisar_erros(request, form)
    return voltar(request, 'calendario:index')


def editar(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    if request.method == 'POST':
        form = EventoForm(request.POST, instance=evento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Evento atualizado.')
            return redirect(url_do_mes(evento.data))
        avisar_erros(request, form)
    return render(request, 'calendario/editar.html', {
        'evento': evento,
        'tipos': Evento.TIPOS,
        'opcoes': opcoes_de_disciplina(),
    })


@require_POST
def excluir(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    evento.delete()
    messages.success(request, f'"{evento.titulo}" excluído.')
    return redirect(url_do_mes(evento.data))


@require_POST
def alternar_concluido(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    evento.concluido = not evento.concluido
    evento.save(update_fields=['concluido'])
    return voltar(request, url_do_mes(evento.data))
