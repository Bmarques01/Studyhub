from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CategoriaForm, DisciplinaForm, PeriodoForm, TopicoForm
from .models import Categoria, Disciplina, Periodo, Topico


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
    return render(request, 'estudos/index.html', {
        'estrutura': estrutura_de_estudos(),
        'tipos': Categoria.TIPOS,
        # para a lista "mover para..." na edição de disciplina
        'todas_categorias': Categoria.objects.prefetch_related('periodos'),
    })


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
        # Sem nome? Sugere o próximo: "3º semestre", "Módulo 2"...
        n = quantidade + 1
        nome = f'Módulo {n}' if categoria.divisao == 'modulo' else f'{n}º semestre'
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
