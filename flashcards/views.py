import json

from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from dashboard.models import Perfil
from estudos.models import Categoria, Disciplina, Topico, semestre_letivo
from estudos.views import avisar_erros, opcoes_de_disciplina

from . import memoria
from .forms import BaralhoForm, EdicaoForm, FlashcardForm, ImportarForm
from .importacao import LIMITE, ler_cartoes
from .models import Flashcard

# Na tela, o tópico da disciplina se chama "baralho": é o mesmo objeto (Topico).
MAX_BARALHOS_NA_CAIXA = 4


# ===== Funções de apoio =====

def ler_id(valor):
    try:
        return int(valor)
    except (ValueError, TypeError):
        return None


def filtro_da_revisao(dados):
    """(disciplina, baralho) escolhidos em ?disciplina=ID&topico=ID. Os dois são opcionais;
    se vier o baralho, a disciplina é a dele."""
    topico = Topico.objects.select_related('disciplina').filter(id=ler_id(dados.get('topico'))).first()
    if topico:
        return topico.disciplina, topico
    return Disciplina.objects.filter(id=ler_id(dados.get('disciplina'))).first(), None


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


def periodos_atuais():
    """Os períodos que você está cursando agora, um por categoria:
    graduação = o semestre letivo de hoje ("2026/2"); pós = o último módulo."""
    atuais = set()
    for categoria in Categoria.objects.prefetch_related('periodos'):
        periodos = list(categoria.periodos.all())
        if categoria.divisao == 'semestre':
            nome = semestre_letivo(timezone.localdate())
            atuais.update(p.id for p in periodos if p.nome == nome)
        elif periodos:
            atuais.add(max(periodos, key=lambda p: (p.ordem, p.id)).id)
    return atuais


def dados_do_dialogo():
    """O que a janela "+ novo" precisa: disciplinas para escolher e os baralhos de cada uma."""
    topicos = {}
    for topico in Topico.objects.order_by('nome'):
        topicos.setdefault(topico.disciplina_id, []).append([topico.id, topico.nome])
    return {'opcoes': opcoes_de_disciplina(), 'topicos': topicos, 'limite_importacao': LIMITE}


# ===== Tela inicial: uma caixa por disciplina =====

def index(request):
    # Link antigo (?disciplina=ID) vai para a página da disciplina
    antiga = Disciplina.objects.filter(id=ler_id(request.GET.get('disciplina'))).first()
    if antiga:
        return redirect('flashcards:disciplina', disciplina_id=antiga.id)

    agora = timezone.now()
    resumo = memoria.resumo_por_disciplina(agora)
    atuais = periodos_atuais()

    # Aparecem: as disciplinas que têm cartões + as que você está cursando agora (mesmo vazias)
    disciplinas = [
        d for d in Disciplina.objects.select_related('categoria', 'periodo').prefetch_related('topicos')
        if d.id in resumo or (not d.arquivada and (d.periodo_id is None or d.periodo_id in atuais))
    ]
    por_baralho = {}  # quantos cartões cada baralho tem
    for linha in Flashcard.objects.values('topico').exclude(topico=None).annotate(n=Count('id')).order_by():
        por_baralho[linha['topico']] = linha['n']

    # Separa em grupos "Categoria · período"; o período atual vem antes dos antigos
    grupos = {}
    for d in sorted(disciplinas, key=lambda d: (
            d.categoria.criado_em, d.categoria_id, d.periodo_id not in atuais,
            -(d.periodo.ordem if d.periodo else 0), d.nome.lower())):
        d.resumo = resumo.get(d.id, {'total': 0, 'para_revisar': 0})
        baralhos = sorted(d.topicos.all(), key=lambda t: (-por_baralho.get(t.id, 0), t.nome.lower()))
        for t in baralhos:
            t.total = por_baralho.get(t.id, 0)
        d.baralhos = baralhos[:MAX_BARALHOS_NA_CAIXA]
        d.mais_baralhos = len(baralhos) - len(d.baralhos)
        rotulo = d.categoria.nome + (f' · {d.periodo.nome}' if d.periodo else '')
        grupo = grupos.setdefault(rotulo, {'rotulo': rotulo, 'atual': d.periodo_id in atuais or not d.periodo,
                                           'disciplinas': []})
        grupo['disciplinas'].append(d)

    return render(request, 'flashcards/index.html', {
        'grupos': list(grupos.values()),
        'total_cartoes': sum(r['total'] for r in resumo.values()),
        'para_revisar': memoria.para_revisar(None, agora),
        'perfil': Perfil.atual(),
        'vagas': memoria.vagas_de_novos(),
        **dados_do_dialogo(),
    })


# ===== Página de uma disciplina: os baralhos e os cartões de cada um =====

def disciplina(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina.objects.select_related('categoria', 'periodo'), id=disciplina_id)
    agora = timezone.now()
    resumo = memoria.resumo_por_baralho(disciplina, agora)
    vazio = {'total': 0, 'para_revisar': 0}

    cartoes = list(disciplina.flashcards.all())
    for cartao in cartoes:
        cartao.situacao = situacao(cartao, agora)

    topicos = list(disciplina.topicos.all())
    baralhos = []  # um bloco por baralho com cartões ("sem baralho" no fim)
    for t in topicos + [None]:
        do_baralho = [c for c in cartoes if c.topico_id == (t.id if t else None)]
        if do_baralho:
            baralhos.append({'topico': t, 'resumo': resumo.get(t.id if t else None, vazio),
                             'cartoes': do_baralho})
    com_cartoes = {c.topico_id for c in cartoes}

    return render(request, 'flashcards/disciplina.html', {
        'disciplina': disciplina,
        'filtro': disciplina,  # deixa a disciplina já escolhida na janela "+ novo"
        'baralhos': baralhos,
        'vazios': [t for t in topicos if t.id not in com_cartoes],
        'topicos_da_disciplina': topicos,
        'total_cartoes': len(cartoes),
        'para_revisar': memoria.para_revisar(disciplina, agora),
        **dados_do_dialogo(),
    })


# ===== Criar, editar, excluir =====

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
def criar_baralho(request):
    """Um baralho novo é um tópico novo na disciplina (aparece também em Estudos e no pomodoro)."""
    form = BaralhoForm(request.POST)
    if not form.is_valid():
        avisar_erros(request, form)
        return voltar(request)
    disciplina, nome = form.cleaned_data['disciplina'], form.cleaned_data['nome']
    topico = disciplina.topicos.filter(nome__iexact=nome).first()
    if topico:
        messages.success(request, f'O baralho "{topico.nome}" já existia em {disciplina.nome}.')
    else:
        topico = Topico.objects.create(disciplina=disciplina, nome=nome)
        messages.success(request, f'Baralho "{topico.nome}" criado em {disciplina.nome}.')
    return redirect(reverse('flashcards:disciplina', args=[disciplina.id]) + f'#baralho-{topico.id}')


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
    limite = ler_id(request.POST.get('flashcards_novos_por_dia')) or 0
    if 1 <= limite <= 500:
        perfil = Perfil.atual()
        perfil.flashcards_novos_por_dia = limite
        perfil.save()
        messages.success(request, f'Agora entram até {limite} cartões novos por dia.')
    else:
        messages.error(request, 'O limite precisa ser um número de 1 a 500.')
    return voltar(request)


# ===== Revisão (tudo, uma disciplina ou um baralho) =====

def revisar(request):
    disciplina, topico = filtro_da_revisao(request.GET)
    return render(request, 'flashcards/revisar.html', {
        'filtro': disciplina,
        'topico': topico,
        'para_revisar': memoria.para_revisar(disciplina, topico=topico),
    })


def estado_da_fila(disciplina, topico=None):
    """O que a tela de revisão precisa: o próximo cartão (ou nenhum) e quantos faltam."""
    agora = timezone.now()
    cartao = memoria.proximo_cartao(disciplina, agora, topico=topico)
    dados = {'restantes': memoria.para_revisar(disciplina, agora, topico=topico), 'cartao': None, 'proxima': ''}
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
        proxima = memoria.proxima_revisao(disciplina, agora, topico=topico)
        if proxima:
            dados['proxima'] = memoria.texto_intervalo(proxima - agora)
    return dados


@require_GET
def proximo(request):
    return JsonResponse(estado_da_fila(*filtro_da_revisao(request.GET)))


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

    # A próxima carta vem do mesmo filtro da revisão (todas, uma disciplina ou um baralho)
    return JsonResponse(estado_da_fila(*filtro_da_revisao(dados)))
