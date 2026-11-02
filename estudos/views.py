from datetime import timedelta

from django.contrib import messages
from django.db.models import Count, Max, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from calendario.models import Evento
from pomodoro.models import SessaoPomodoro

from .forms import CategoriaForm, DisciplinaForm, NotasForm, PeriodoForm, TopicoForm
from .models import Categoria, Disciplina, Periodo, Topico, proximo_letivo, semestre_letivo


# ===== Funções de apoio =====

def estrutura_de_estudos():
    """Monta a árvore Categoria → Períodos → Disciplinas para mostrar na tela.

    Cada categoria vira um dicionário:
      'grupos':     um por período (+ "sem período"), cada um com suas disciplinas ativas
      'arquivadas': disciplinas arquivadas da categoria inteira
    """
    # prefetch_related busca tudo em poucas consultas ao banco, em vez de uma por item
    categorias = Categoria.objects.prefetch_related('periodos', 'disciplinas__topicos')
    estrutura = []
    for categoria in categorias:
        disciplinas = list(categoria.disciplinas.all())
        ativas = [d for d in disciplinas if not d.arquivada]

        grupos = [
            {'periodo': p, 'disciplinas': [d for d in ativas if d.periodo_id == p.id]}
            for p in categoria.periodos.all()
        ]
        soltas = [d for d in ativas if d.periodo_id is None]
        # O grupo "sem período" aparece se a categoria não tem divisão ou se há disciplinas nele
        if not categoria.divisao or soltas:
            grupos.append({'periodo': None, 'disciplinas': soltas})

        estrutura.append({
            'categoria': categoria,
            'grupos': grupos,
            'arquivadas': [d for d in disciplinas if d.arquivada],
        })
    return estrutura


def opcoes_de_disciplina():
    """Para o pomodoro: grupos de disciplinas ativas, já com o nome do grupo.
    Ex.: ('Ciência da Computação · 5º semestre', [Redes 2, ...])"""
    opcoes = []
    for item in estrutura_de_estudos():
        for grupo in item['grupos']:
            if grupo['disciplinas']:
                rotulo = item['categoria'].nome
                if grupo['periodo']:
                    rotulo += f' · {grupo["periodo"].nome}'
                opcoes.append((rotulo, grupo['disciplinas']))
    return opcoes


def avisar_erros(request, form):
    """Mostra os erros do formulário como mensagem (ex.: nome vazio, cor inválida)."""
    for erros in form.errors.values():
        for erro in erros:
            messages.error(request, erro)


def salvar_ou_avisar(request, form):
    if form.is_valid():
        return form.save()
    avisar_erros(request, form)
    return None


# ===== Página =====

def index(request):
    estrutura = estrutura_de_estudos()

    # Números para os cartões: minutos estudados e próximo evento de cada disciplina
    minutos = dict(SessaoPomodoro.objects.filter(disciplina__isnull=False)
                   .values('disciplina').annotate(total=Sum('duracao_minutos'))
                   .values_list('disciplina', 'total'))
    proximo = {}
    for evento in Evento.objects.filter(data__gte=timezone.localdate(), concluido=False,
                                        disciplina__isnull=False):
        proximo.setdefault(evento.disciplina_id, evento)  # já vem em ordem de data: fica o primeiro

    for item in estrutura:
        periodos = [g for g in item['grupos'] if g['periodo']]
        for grupo in item['grupos']:
            for d in grupo['disciplinas']:
                d.minutos = minutos.get(d.id, 0)
                d.proximo = proximo.get(d.id)
            grupo['minutos'] = sum(d.minutos for d in grupo['disciplinas'])
            # o semestre/módulo mais recente começa aberto
            grupo['recente'] = bool(periodos) and grupo is periodos[-1]

    return render(request, 'estudos/index.html', {
        'estrutura': estrutura,
        'tipos': Categoria.TIPOS,
        # para a lista "mover para..." na edição de disciplina
        'todas_categorias': Categoria.objects.prefetch_related('periodos'),
    })


# ===== Página da disciplina =====

def disciplina_detalhe(request, disciplina_id):
    disciplina = get_object_or_404(
        Disciplina.objects.select_related('categoria', 'periodo'), id=disciplina_id)
    hoje = timezone.localdate()
    sessoes = SessaoPomodoro.objects.filter(disciplina=disciplina)

    resumo = sessoes.aggregate(total=Sum('duracao_minutos'), quantidade=Count('id'),
                               ultima=Max('concluida_em'))
    minutos_mes = sessoes.filter(concluida_em__date__gte=hoje.replace(day=1)).aggregate(
        total=Sum('duracao_minutos'))['total'] or 0
    ultimo_dia = timezone.localtime(resumo['ultima']).date() if resumo['ultima'] else None

    # --- Últimas 8 semanas (colunas), semanas começando na segunda ---
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    inicio = inicio_semana - timedelta(weeks=7)
    por_dia = (sessoes.filter(concluida_em__date__gte=inicio)
               .annotate(dia=TruncDate('concluida_em')).values('dia')
               .annotate(total=Sum('duracao_minutos')))
    semanas = [{'inicio': inicio + timedelta(weeks=i), 'minutos': 0} for i in range(8)]
    for linha in por_dia:
        semanas[(linha['dia'] - inicio).days // 7]['minutos'] += linha['total']
    topo = max(60, -(-max(s['minutos'] for s in semanas) // 60) * 60)  # arredonda para cima, em horas
    for semana in semanas:
        semana['altura'] = semana['minutos'] / topo * 100
        semana['atual'] = semana['inicio'] == inicio_semana

    # --- Tempo por tópico (inclui tópicos ainda não estudados) ---
    por_topico = {
        linha['topico']: linha
        for linha in sessoes.filter(topico__isnull=False).values('topico')
        .annotate(total=Sum('duracao_minutos'), ultima=Max('concluida_em'))
    }
    topicos = []
    for topico in disciplina.topicos.all():
        linha = por_topico.get(topico.id, {})
        ultima = linha.get('ultima')
        topicos.append({
            'topico': topico,
            'minutos': linha.get('total', 0),
            'dias_sem_estudar': (hoje - timezone.localtime(ultima).date()).days if ultima else None,
        })
    topicos.sort(key=lambda t: -t['minutos'])
    sem_topico = sessoes.filter(topico__isnull=True).aggregate(total=Sum('duracao_minutos'))['total'] or 0
    maior = max([t['minutos'] for t in topicos] + [sem_topico, 1])
    for t in topicos:
        t['largura'] = t['minutos'] / maior * 100

    return render(request, 'estudos/disciplina.html', {
        'disciplina': disciplina,
        'na_grade': getattr(disciplina, 'na_grade', None),  # a disciplina correspondente na grade do curso
        'hoje': hoje,
        'minutos_total': resumo['total'] or 0,
        'minutos_mes': minutos_mes,
        'quantidade_sessoes': resumo['quantidade'],
        'ultimo_dia': ultimo_dia,
        'dias_desde_ultimo': (hoje - ultimo_dia).days if ultimo_dia else None,
        'semanas': semanas,
        'marcas_eixo': [topo, topo // 2, 0],
        'topicos': topicos,
        'sem_topico': sem_topico,
        'largura_sem_topico': sem_topico / maior * 100,
        'proximos': Evento.objects.filter(disciplina=disciplina, data__gte=hoje, concluido=False),
        'historico': sessoes.select_related('topico')[:8],
    })


@require_POST
def salvar_notas(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina, id=disciplina_id)
    form = NotasForm(request.POST, instance=disciplina)
    if form.is_valid():
        form.save()
        messages.success(request, 'Notas salvas.')
    else:
        avisar_erros(request, form)
    return redirect('estudos:disciplina', disciplina_id=disciplina.id)


# ===== Categorias =====

@require_POST
def criar_categoria(request):
    categoria = salvar_ou_avisar(request, CategoriaForm(request.POST))
    if categoria:
        messages.success(request, f'Categoria "{categoria.nome}" criada.')
    return redirect('estudos:index')


@require_POST
def editar_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    # instance=categoria: o formulário altera essa categoria em vez de criar uma nova
    salvar_ou_avisar(request, CategoriaForm(request.POST, instance=categoria))
    return redirect('estudos:index')


@require_POST
def excluir_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    categoria.delete()
    messages.success(request, f'Categoria "{categoria.nome}" excluída.')
    return redirect('estudos:index')


# ===== Períodos (semestres / módulos) =====

@require_POST
def criar_periodo(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    quantidade = categoria.periodos.count()
    nome = request.POST.get('nome', '').strip()
    if not nome:
        if categoria.divisao == 'modulo':
            # Sem nome? Próximo módulo: "Módulo 1", "Módulo 2"...
            nome = f'Módulo {quantidade + 1}'
        else:
            # Graduação: semestre letivo atual ("2026/2"); se já existir, o seguinte
            existentes = set(categoria.periodos.values_list('nome', flat=True))
            nome = semestre_letivo(timezone.localdate())
            while nome in existentes:
                nome = proximo_letivo(nome)
    Periodo.objects.create(categoria=categoria, nome=nome[:100], ordem=quantidade + 1)
    return redirect('estudos:index')


@require_POST
def editar_periodo(request, periodo_id):
    periodo = get_object_or_404(Periodo, id=periodo_id)
    salvar_ou_avisar(request, PeriodoForm(request.POST, instance=periodo))
    return redirect('estudos:index')


@require_POST
def excluir_periodo(request, periodo_id):
    periodo = get_object_or_404(Periodo, id=periodo_id)
    periodo.delete()  # as disciplinas dele não são apagadas: ficam "sem período"
    messages.success(request, f'"{periodo.nome}" excluído.')
    return redirect('estudos:index')


# ===== Disciplinas =====

def ler_local(valor):
    """O campo "local" vem como 'c:3' (categoria 3, sem período) ou 'p:7' (período 7).
    Devolve (categoria, periodo) ou (None, None) se for inválido."""
    tipo, _, id_ = (valor or '').partition(':')
    if not id_.isdigit():
        return None, None
    if tipo == 'p':
        periodo = Periodo.objects.select_related('categoria').filter(id=id_).first()
        return (periodo.categoria, periodo) if periodo else (None, None)
    if tipo == 'c':
        return Categoria.objects.filter(id=id_).first(), None
    return None, None


@require_POST
def criar_disciplina(request):
    categoria, periodo = ler_local(request.POST.get('local'))
    if not categoria:
        messages.error(request, 'Escolha onde colocar a disciplina.')
        return redirect('estudos:index')

    form = DisciplinaForm(request.POST)
    if form.is_valid():
        disciplina = form.save(commit=False)  # ainda não salva: falta dizer onde ela fica
        disciplina.categoria = categoria
        disciplina.periodo = periodo
        disciplina.save()
        messages.success(request, f'Disciplina "{disciplina.nome}" criada.')
    else:
        avisar_erros(request, form)
    return redirect('estudos:index')


@require_POST
def editar_disciplina(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina, id=disciplina_id)
    categoria, periodo = ler_local(request.POST.get('local'))
    if not categoria:
        messages.error(request, 'Escolha onde colocar a disciplina.')
        return redirect('estudos:index')

    form = DisciplinaForm(request.POST, instance=disciplina)
    if form.is_valid():
        disciplina = form.save(commit=False)
        disciplina.categoria = categoria
        disciplina.periodo = periodo
        disciplina.save()
    else:
        avisar_erros(request, form)
    return redirect('estudos:index')


@require_POST
def arquivar_disciplina(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina, id=disciplina_id)
    disciplina.arquivada = not disciplina.arquivada
    disciplina.save()
    acao = 'arquivada' if disciplina.arquivada else 'reativada'
    messages.success(request, f'Disciplina "{disciplina.nome}" {acao}.')
    return redirect('estudos:index')


@require_POST
def excluir_disciplina(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina, id=disciplina_id)
    disciplina.delete()
    messages.success(request, f'Disciplina "{disciplina.nome}" excluída.')
    return redirect('estudos:index')


# ===== Tópicos =====

@require_POST
def criar_topico(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina, id=disciplina_id)
    form = TopicoForm(request.POST)
    if form.is_valid():
        topico = form.save(commit=False)
        topico.disciplina = disciplina
        topico.save()
    else:
        avisar_erros(request, form)
    # Volta para a página de onde veio (ex.: a página da disciplina), se for do próprio site
    destino = request.POST.get('proximo')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect('estudos:index')


@require_POST
def editar_topico(request, topico_id):
    topico = get_object_or_404(Topico, id=topico_id)
    salvar_ou_avisar(request, TopicoForm(request.POST, instance=topico))
    return redirect('estudos:index')


@require_POST
def excluir_topico(request, topico_id):
    get_object_or_404(Topico, id=topico_id).delete()
    return redirect('estudos:index')
