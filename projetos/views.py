import json
from datetime import timedelta

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from estudos.views import avisar_erros
from pomodoro.models import SessaoPomodoro

from .forms import (EntradaDiarioForm, FuncionalidadeForm, NovaFuncionalidadeForm, ProjetoForm,
                    TarefaForm)
from .models import EntradaDiario, Funcionalidade, Projeto, Tarefa


# ===== Funções de apoio =====

def progresso(feitas, total):
    return round(feitas / total * 100) if total else 0


def opcoes_de_projeto():
    """Para o pomodoro: projetos em andamento, cada um com as funcionalidades ainda não feitas
    (primeiro as que estão em "fazendo")."""
    ordem = {'fazendo': 0, 'a_fazer': 1, 'backlog': 2}
    projetos = (Projeto.objects.filter(status__in=['ativo', 'ideia'])
                .prefetch_related('funcionalidades'))
    resultado = []
    for projeto in projetos:
        pendentes = [f for f in projeto.funcionalidades.all() if f.status != 'feito']
        pendentes.sort(key=lambda f: (ordem[f.status], f.ordem, f.id))
        resultado.append((projeto, pendentes))
    return resultado


# ===== Lista de projetos =====

def index(request):
    minutos = dict(SessaoPomodoro.objects.filter(projeto__isnull=False)
                   .values('projeto').annotate(total=Sum('duracao_minutos'))
                   .values_list('projeto', 'total'))
    projetos = Projeto.objects.annotate(
        total=Count('funcionalidades'),
        feitas=Count('funcionalidades', filter=Q(funcionalidades__status='feito')),
        fazendo=Count('funcionalidades', filter=Q(funcionalidades__status='fazendo')),
    ).order_by('criado_em')
    for projeto in projetos:
        projeto.minutos = minutos.get(projeto.id, 0)
        projeto.progresso = progresso(projeto.feitas, projeto.total)
    return render(request, 'projetos/index.html', {
        'projetos': projetos,
        'status': Projeto.STATUS,
    })


@require_POST
def criar_projeto(request):
    form = ProjetoForm(request.POST)
    if form.is_valid():
        projeto = form.save()
        return redirect('projetos:projeto', projeto_id=projeto.id)
    avisar_erros(request, form)
    return redirect('projetos:index')


# ===== Página do projeto (Kanban) =====

def projeto(request, projeto_id):
    projeto = get_object_or_404(Projeto, id=projeto_id)
    hoje = timezone.localdate()

    sessoes = SessaoPomodoro.objects.filter(projeto=projeto)
    minutos_por_funcionalidade = dict(
        sessoes.filter(funcionalidade__isnull=False).values('funcionalidade')
        .annotate(total=Sum('duracao_minutos')).values_list('funcionalidade', 'total'))

    # order_by explícito: em consultas com Count o Django ignora a ordenação padrão do model
    funcionalidades = projeto.funcionalidades.annotate(
        total_tarefas=Count('tarefas'),
        tarefas_feitas=Count('tarefas', filter=Q(tarefas__feita=True)),
    ).order_by('ordem', 'id')
    colunas = []
    for status, nome in Funcionalidade.STATUS:
        cartoes = [f for f in funcionalidades if f.status == status]
        if status == 'feito':
            # "feito" vira uma pilha: o que terminou por último fica em cima (sem data vai para o fim)
            cartoes.sort(key=lambda f: (f.concluida_em is not None, f.concluida_em, f.id), reverse=True)
        for f in cartoes:
            f.minutos = minutos_por_funcionalidade.get(f.id, 0)
        colunas.append({'status': status, 'nome': nome, 'cartoes': cartoes})

    total = len(funcionalidades)
    feitas = sum(1 for f in funcionalidades if f.status == 'feito')
    inicio_semana = hoje - timedelta(days=hoje.weekday())

    return render(request, 'projetos/projeto.html', {
        'projeto': projeto,
        'colunas': colunas,
        'total': total,
        'feitas': feitas,
        'progresso': progresso(feitas, total),
        'minutos_total': sessoes.aggregate(t=Sum('duracao_minutos'))['t'] or 0,
        'minutos_semana': sessoes.filter(concluida_em__date__gte=inicio_semana)
                                 .aggregate(t=Sum('duracao_minutos'))['t'] or 0,
        'diario': projeto.diario.all()[:10],
        'form_projeto': ProjetoForm(instance=projeto),
        'tipos': Funcionalidade.TIPOS,
        'prioridades': Funcionalidade.PRIORIDADES,
        'status_projeto': Projeto.STATUS,
        'tipos_projeto': Projeto.TIPOS,
        'hoje': hoje,
    })


@require_POST
def editar_projeto(request, projeto_id):
    projeto = get_object_or_404(Projeto, id=projeto_id)
    form = ProjetoForm(request.POST, instance=projeto)
    if form.is_valid():
        form.save()
        messages.success(request, 'Projeto atualizado.')
    else:
        avisar_erros(request, form)
    return redirect('projetos:projeto', projeto_id=projeto.id)


@require_POST
def excluir_projeto(request, projeto_id):
    projeto = get_object_or_404(Projeto, id=projeto_id)
    projeto.delete()
    messages.success(request, f'Projeto "{projeto.nome}" excluído.')
    return redirect('projetos:index')


# ===== Funcionalidades =====

@require_POST
def criar_funcionalidade(request, projeto_id):
    projeto = get_object_or_404(Projeto, id=projeto_id)
    form = NovaFuncionalidadeForm(request.POST)
    if form.is_valid():
        funcionalidade = form.save(commit=False)
        funcionalidade.projeto = projeto
        # entra no fim da coluna
        ultima = projeto.funcionalidades.filter(status=funcionalidade.status).order_by('-ordem').first()
        funcionalidade.ordem = (ultima.ordem + 1) if ultima else 0
        funcionalidade.save()
    else:
        avisar_erros(request, form)
    return redirect('projetos:projeto', projeto_id=projeto.id)


def funcionalidade(request, funcionalidade_id):
    item = get_object_or_404(Funcionalidade.objects.select_related('projeto'), id=funcionalidade_id)
    if request.method == 'POST':
        form = FuncionalidadeForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Funcionalidade atualizada.')
            return redirect('projetos:funcionalidade', funcionalidade_id=item.id)
        avisar_erros(request, form)
    minutos = item.minutos_trabalhados
    estimativa_min = int(item.estimativa_horas * 60) if item.estimativa_horas else None
    return render(request, 'projetos/funcionalidade.html', {
        'item': item,
        'tarefas': item.tarefas.all(),
        'minutos': minutos,
        'estimativa_min': estimativa_min,
        'pct_estimativa': round(minutos / estimativa_min * 100) if estimativa_min else None,
        'sessoes': item.sessoes.all()[:10],
        'tipos': Funcionalidade.TIPOS,
        'prioridades': Funcionalidade.PRIORIDADES,
        'status': Funcionalidade.STATUS,
    })


@require_POST
def mover_funcionalidade(request, funcionalidade_id):
    """Chamada pelo arrastar e soltar do Kanban: muda a coluna e a ordem dos cartões."""
    item = get_object_or_404(Funcionalidade, id=funcionalidade_id)
    try:
        dados = json.loads(request.body)
        status = dados['status']
        ids = [int(i) for i in dados.get('ordem', [])]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'erro': 'dados inválidos'}, status=400)
    if status not in dict(Funcionalidade.STATUS):
        return JsonResponse({'erro': 'coluna inválida'}, status=400)

    item.status = status
    item.save()
    # reordena os cartões da coluna na ordem em que ficaram na tela
    cartoes = {f.id: f for f in item.projeto.funcionalidades.filter(id__in=ids)}
    for posicao, cartao_id in enumerate(ids):
        if cartao_id in cartoes:
            Funcionalidade.objects.filter(id=cartao_id).update(ordem=posicao)
    return JsonResponse({'ok': True, 'status': item.status})


@require_POST
def excluir_funcionalidade(request, funcionalidade_id):
    item = get_object_or_404(Funcionalidade, id=funcionalidade_id)
    projeto_id = item.projeto_id
    item.delete()
    messages.success(request, f'"{item.titulo}" excluída.')
    return redirect('projetos:projeto', projeto_id=projeto_id)


# ===== Tarefas (checklist) =====

@require_POST
def criar_tarefa(request, funcionalidade_id):
    item = get_object_or_404(Funcionalidade, id=funcionalidade_id)
    form = TarefaForm(request.POST)
    if form.is_valid():
        tarefa = form.save(commit=False)
        tarefa.funcionalidade = item
        tarefa.save()
    return redirect('projetos:funcionalidade', funcionalidade_id=item.id)


@require_POST
def alternar_tarefa(request, tarefa_id):
    tarefa = get_object_or_404(Tarefa, id=tarefa_id)
    tarefa.feita = not tarefa.feita
    tarefa.save(update_fields=['feita'])
    return redirect('projetos:funcionalidade', funcionalidade_id=tarefa.funcionalidade_id)


@require_POST
def excluir_tarefa(request, tarefa_id):
    tarefa = get_object_or_404(Tarefa, id=tarefa_id)
    tarefa.delete()
    return redirect('projetos:funcionalidade', funcionalidade_id=tarefa.funcionalidade_id)


# ===== Diário de bordo =====

@require_POST
def criar_entrada(request, projeto_id):
    projeto = get_object_or_404(Projeto, id=projeto_id)
    form = EntradaDiarioForm(request.POST)
    if form.is_valid():
        entrada = form.save(commit=False)
        entrada.projeto = projeto
        entrada.save()
        messages.success(request, 'Anotado no diário.')
    else:
        avisar_erros(request, form)
    return redirect(f"{projeto_url(projeto)}#diario")


@require_POST
def excluir_entrada(request, entrada_id):
    entrada = get_object_or_404(EntradaDiario, id=entrada_id)
    entrada.delete()
    return redirect(f"{projeto_url(entrada.projeto)}#diario")


def projeto_url(projeto):
    return reverse('projetos:projeto', args=[projeto.id])
