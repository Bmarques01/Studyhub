import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from dashboard.models import Perfil
from estudos.models import Disciplina, Topico
from estudos.views import avisar_erros, opcoes_de_disciplina

from . import memoria
from .forms import EdicaoForm, FlashcardForm, ImportarForm
from .importacao import LIMITE, ler_cartoes
from .models import Flashcard


# ===== Funções de apoio =====

def disciplina_do_filtro(request):
    """A disciplina escolhida em ?disciplina=ID (ou None = todas)."""
    try:
        return Disciplina.objects.get(id=int(request.GET.get('disciplina', '')))
    except (ValueError, Disciplina.DoesNotExist):
        return None


def voltar(request):
    """Volta para a página de onde o formulário foi enviado (só se for deste site)."""
    proximo = request.POST.get('proximo', '')
    if url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
        return redirect(proximo)
    return redirect('flashcards:index')


def situacao(cartao, agora):
    """Texto da lista: 'novo', 'para revisar' ou 'em 3 dias'."""
    if cartao.novo:
        return 'novo'
    if cartao.vencimento <= agora:
        return 'para revisar'
    return 'em ' + memoria.texto_intervalo(cartao.vencimento - agora)


# ===== Página principal: lista com filtro por disciplina =====

def index(request):
    agora = timezone.now()
    filtro = disciplina_do_filtro(request)
    resumo = memoria.resumo_por_disciplina(agora)

    # Botões de filtro: só as disciplinas que têm cartões (e a escolhida, mesmo vazia)
    ids = set(resumo) | ({filtro.id} if filtro else set())
    filtros = list(Disciplina.objects.filter(id__in=ids).order_by('nome'))
    for d in filtros:
        d.resumo = resumo.get(d.id, {'total': 0, 'para_revisar': 0})

    cartoes = list(memoria.do_filtro(filtro).select_related('disciplina', 'topico')
                   .prefetch_related('disciplina__topicos'))  # tópicos para a edição
    for cartao in cartoes:
        cartao.situacao = situacao(cartao, agora)

    # Para o JavaScript trocar a lista de tópicos quando a disciplina muda
    topicos = {}
    for topico in Topico.objects.order_by('nome'):
        topicos.setdefault(topico.disciplina_id, []).append([topico.id, topico.nome])

    return render(request, 'flashcards/index.html', {
        'filtro': filtro,
        'filtros': filtros,
        'total_cartoes': sum(r['total'] for r in resumo.values()),
        'para_revisar': memoria.para_revisar(filtro, agora),
        'para_revisar_todas': memoria.para_revisar(None, agora),
        'cartoes': cartoes,
        'opcoes': opcoes_de_disciplina(),
        'topicos': topicos,
        'perfil': Perfil.atual(),
        'vagas': memoria.vagas_de_novos(),
        'limite_importacao': LIMITE,
    })


@require_POST
def criar(request):
    form = FlashcardForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cartão criado.')
    else:
        avisar_erros(request, form)
    return voltar(request)


@require_POST
def importar(request):
    form = ImportarForm(request.POST)
    if not form.is_valid():
        avisar_erros(request, form)
        return voltar(request)

    cartoes, problemas = ler_cartoes(form.cleaned_data['texto'])
    if len(cartoes) > LIMITE:
        messages.error(request, f'São {len(cartoes)} cartões: cole no máximo {LIMITE} por vez.')
        return voltar(request)

    disciplina, topico = form.cleaned_data['disciplina'], form.cleaned_data['topico']
    Flashcard.objects.bulk_create([
        Flashcard(disciplina=disciplina, topico=topico, frente=frente, verso=verso)
        for frente, verso in cartoes
    ])
    if cartoes:
        messages.success(request, f'{len(cartoes)} cartão(ões) criado(s) em {disciplina.nome}.')
    if problemas:
        messages.error(request, f'{len(problemas)} bloco(s) ignorado(s) por faltar "F:" ou "V:": '
                                + '; '.join(f'"{p}"' for p in problemas[:5]))
    if not cartoes and not problemas:
        messages.error(request, 'Não encontrei nenhum cartão. Use o formato "F: pergunta" e "V: resposta".')
    return voltar(request)


@require_POST
def editar(request, cartao_id):
    cartao = get_object_or_404(Flashcard, id=cartao_id)
    form = EdicaoForm(request.POST, instance=cartao)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cartão salvo.')
    else:
        avisar_erros(request, form)
    return voltar(request)


@require_POST
def excluir(request, cartao_id):
    get_object_or_404(Flashcard, id=cartao_id).delete()
    messages.success(request, 'Cartão excluído.')
    return voltar(request)


@require_POST
def salvar_limite(request):
    try:
        limite = int(request.POST.get('flashcards_novos_por_dia', ''))
    except ValueError:
        limite = 0
    if 1 <= limite <= 500:
        perfil = Perfil.atual()
        perfil.flashcards_novos_por_dia = limite
        perfil.save()
        messages.success(request, f'Agora entram até {limite} cartões novos por dia.')
    else:
        messages.error(request, 'O limite precisa ser um número de 1 a 500.')
    return voltar(request)


# ===== Revisão =====

def revisar(request):
    filtro = disciplina_do_filtro(request)
    return render(request, 'flashcards/revisar.html', {
        'filtro': filtro,
        'para_revisar': memoria.para_revisar(filtro),
    })


def estado_da_fila(disciplina):
    """O que a tela de revisão precisa: o próximo cartão (ou nenhum) e quantos faltam."""
    agora = timezone.now()
    cartao = memoria.proximo_cartao(disciplina, agora)
    dados = {'restantes': memoria.para_revisar(disciplina, agora), 'cartao': None, 'proxima': ''}
    if cartao:
        dados['cartao'] = {
            'id': cartao.id,
            'frente': cartao.frente,
            'verso': cartao.verso,
            'disciplina': cartao.disciplina.nome,
            'cor': cartao.disciplina.cor,
            'topico': cartao.topico.nome if cartao.topico else '',
            'novo': cartao.novo,
            'intervalos': memoria.intervalos(cartao, agora),
        }
    else:
        proxima = memoria.proxima_revisao(disciplina, agora)
        if proxima:
            dados['proxima'] = memoria.texto_intervalo(proxima - agora)
    return dados


@require_GET
def proximo(request):
    return JsonResponse(estado_da_fila(disciplina_do_filtro(request)))


@require_POST
def responder(request, cartao_id):
    """Chamada pelo JavaScript ao clicar em de novo / difícil / bom / fácil."""
    cartao = get_object_or_404(Flashcard, id=cartao_id)
    try:
        dados = json.loads(request.body)
        nota = int(dados['nota'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'erro': 'dados inválidos'}, status=400)
    if nota not in (1, 2, 3, 4):
        return JsonResponse({'erro': 'nota inválida'}, status=400)

    try:
        duracao = min(int(dados.get('duracao_segundos')), 3600)
    except (ValueError, TypeError):
        duracao = None
    memoria.responder(cartao, nota, duracao_segundos=duracao if duracao and duracao > 0 else None)

    # A próxima carta vem do mesmo filtro da revisão (uma disciplina ou todas)
    try:
        disciplina = Disciplina.objects.filter(id=int(dados.get('disciplina'))).first()
    except (ValueError, TypeError):
        disciplina = None
    return JsonResponse(estado_da_fila(disciplina))
