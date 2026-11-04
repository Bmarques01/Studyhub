import random

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from estudos.models import Disciplina, Topico
from estudos.views import avisar_erros, opcoes_de_disciplina
from flashcards.views import ler_id, periodos_atuais

from .forms import ImportarForm, QuestaoForm, QuestionarioForm
from .importacao import LIMITE, MAX_ALTERNATIVAS, ler_questoes
from .models import Alternativa, Questao, Questionario, Resposta

ALTERNATIVAS_NO_FORMULARIO = 4  # espaços em branco ao escrever uma questão nova


# ===== Funções de apoio =====

def acertos_por(campo, filtro=None):
    """{id: {'respostas': n, 'acertos': n}} agrupando as respostas por `campo`
    (ex.: 'questao__disciplina' ou 'questao')."""
    linhas = (Resposta.objects.filter(**(filtro or {})).values(campo)
              .annotate(respostas=Count('id'), acertos=Count('id', filter=Q(acertou=True))).order_by())
    return {linha[campo]: linha for linha in linhas}


def porcentagem(acertos, total):
    return round(100 * acertos / total) if total else None


def topicos_por_disciplina():
    """Para o JavaScript trocar a lista de tópicos quando muda a disciplina."""
    topicos = {}
    for topico in Topico.objects.order_by('nome'):
        topicos.setdefault(topico.disciplina_id, []).append([topico.id, topico.nome])
    return topicos


@transaction.atomic
def salvar_questao(questao, dados):
    """Grava a questão e troca as alternativas pelas novas (na ordem A, B, C...)."""
    questao.disciplina = dados['disciplina']
    questao.topico = dados.get('topico')
    questao.tipo = dados['tipo']
    questao.enunciado = dados['enunciado'].strip()
    questao.explicacao = (dados.get('explicacao') or '').strip()
    questao.resposta = dados.get('resposta', '')
    questao.save()
    questao.alternativas.all().delete()
    Alternativa.objects.bulk_create([
        Alternativa(questao=questao, texto=texto, correta=certa, ordem=i)
        for i, (texto, certa) in enumerate(dados.get('alternativas', []))
    ])
    return questao


# ===== Tela inicial: uma caixa por disciplina =====

def index(request):
    total_por_disciplina = dict(Questao.objects.values_list('disciplina').annotate(n=Count('id')).order_by())
    acertos = acertos_por('questao__disciplina')
    atuais = periodos_atuais()

    # Aparecem: as disciplinas que têm questões + as que você está cursando agora (mesmo vazias)
    disciplinas = [
        d for d in Disciplina.objects.select_related('categoria', 'periodo')
        if d.id in total_por_disciplina or (not d.arquivada and (d.periodo_id is None or d.periodo_id in atuais))
    ]
    grupos = {}
    for d in sorted(disciplinas, key=lambda d: (
            d.categoria.criado_em, d.categoria_id, d.periodo_id not in atuais,
            -(d.periodo.ordem if d.periodo else 0), d.nome.lower())):
        d.total = total_por_disciplina.get(d.id, 0)
        linha = acertos.get(d.id, {'respostas': 0, 'acertos': 0})
        d.respostas = linha['respostas']
        d.aproveitamento = porcentagem(linha['acertos'], linha['respostas'])
        rotulo = d.categoria.nome + (f' · {d.periodo.nome}' if d.periodo else '')
        grupo = grupos.setdefault(rotulo, {'rotulo': rotulo, 'atual': d.periodo_id in atuais or not d.periodo,
                                           'disciplinas': []})
        grupo['disciplinas'].append(d)

    return render(request, 'questoes/index.html', {
        'grupos': list(grupos.values()),
        'total_questoes': sum(total_por_disciplina.values()),
    })


# ===== Página de uma disciplina: as questões, separadas por tópico =====

def disciplina(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina.objects.select_related('categoria', 'periodo'), id=disciplina_id)
    questoes = list(disciplina.questoes.select_related('topico').prefetch_related('alternativas'))
    acertos = acertos_por('questao', {'questao__disciplina': disciplina})
    for questao in questoes:
        linha = acertos.get(questao.id, {'respostas': 0, 'acertos': 0})
        questao.respostas_feitas, questao.acertos = linha['respostas'], linha['acertos']

    # um bloco por tópico (em ordem alfabética); as sem tópico vão por último
    blocos = {}
    for questao in sorted(questoes, key=lambda q: (q.topico is None, q.topico.nome.lower() if q.topico else '')):
        blocos.setdefault(questao.topico_id, {'topico': questao.topico, 'questoes': []})['questoes'].append(questao)

    contagem = {}
    for questao in questoes:
        contagem[questao.topico_id] = contagem.get(questao.topico_id, 0) + 1
    topicos = [(t, contagem[t.id]) for t in disciplina.topicos.order_by('nome') if t.id in contagem]

    questionarios = []
    for q in disciplina.questionarios.select_related('topico').annotate(
            feitas=Count('respostas'), certas=Count('respostas', filter=Q(respostas__acertou=True)))[:5]:
        q.total = len(q.questoes)
        questionarios.append(q)

    return render(request, 'questoes/disciplina.html', {
        'disciplina': disciplina,
        'blocos': list(blocos.values()),
        'total_questoes': len(questoes),
        'topicos': topicos,
        'quantidades': QuestionarioForm.QUANTIDADES,
        'questionarios': questionarios,
    })


# ===== Escrever / editar uma questão =====

def valores_da_questao(questao):
    """O que o formulário mostra ao editar uma questão que já existe."""
    alternativas = [(a.texto, a.correta) for a in questao.alternativas.all()]
    return {
        'disciplina': questao.disciplina_id, 'topico': questao.topico_id or '', 'tipo': questao.tipo,
        'enunciado': questao.enunciado, 'explicacao': questao.explicacao,
        'resposta_vf': questao.resposta if questao.tipo == 'vf' else '',
        'resposta_aberta': questao.resposta if questao.tipo == 'aberta' else '',
        'alternativas': alternativas,
    }


def valores_enviados(post):
    """O que você tinha digitado, para não perder nada quando o formulário volta com erro."""
    certa = ler_id(post.get('correta'))
    return {
        'disciplina': ler_id(post.get('disciplina')), 'topico': ler_id(post.get('topico')) or '',
        'tipo': post.get('tipo', 'multipla'), 'enunciado': post.get('enunciado', ''),
        'explicacao': post.get('explicacao', ''), 'resposta_vf': post.get('resposta_vf', ''),
        'resposta_aberta': post.get('resposta_aberta', ''),
        'alternativas': [(texto, i == certa) for i, texto in enumerate(post.getlist('alternativa')[:MAX_ALTERNATIVAS])],
    }


def formulario(request, questao=None):
    """Mesma tela para escrever uma questão nova e para editar."""
    if request.method == 'POST':
        form = QuestaoForm(request.POST)
        if form.is_valid():
            salva = salvar_questao(questao or Questao(), form.cleaned_data)
            if questao:
                messages.success(request, 'Questão atualizada.')
            elif 'outra' in request.POST:
                # "salvar e escrever outra": volta para o formulário na mesma disciplina e tópico
                messages.success(request, 'Questão salva. Pode escrever a próxima.')
                destino = reverse('questoes:nova') + f'?disciplina={salva.disciplina_id}&tipo={salva.tipo}'
                return redirect(destino + (f'&topico={salva.topico_id}' if salva.topico_id else ''))
            else:
                messages.success(request, 'Questão salva.')
            return redirect(reverse('questoes:disciplina', args=[salva.disciplina_id]) + f'#questao-{salva.id}')
        valores = valores_enviados(request.POST)
        erros = [erro for lista in form.errors.values() for erro in lista]
    elif questao:
        valores, erros = valores_da_questao(questao), []
    else:
        tipo = request.GET.get('tipo')
        valores = {
            'disciplina': ler_id(request.GET.get('disciplina')), 'topico': ler_id(request.GET.get('topico')) or '',
            'tipo': tipo if tipo in dict(Questao.TIPOS) else 'multipla', 'alternativas': [],
        }
        erros = []

    # sempre pelo menos 4 espaços de alternativa (o botão "+ alternativa" cria mais, até 8)
    alternativas = list(valores.get('alternativas', []))
    alternativas += [('', False)] * (ALTERNATIVAS_NO_FORMULARIO - len(alternativas))
    valores['alternativas'] = [(chr(65 + i), i, texto, certa) for i, (texto, certa) in enumerate(alternativas)]

    voltar = valores.get('disciplina')
    return render(request, 'questoes/form.html', {
        'questao': questao,
        'valores': valores,
        'erros': erros,
        'opcoes': opcoes_de_disciplina(),
        'topicos': topicos_por_disciplina(),
        'tipos': Questao.TIPOS,
        'max_alternativas': MAX_ALTERNATIVAS,
        'voltar': reverse('questoes:disciplina', args=[voltar]) if voltar and Disciplina.objects.filter(id=voltar).exists()
        else reverse('questoes:index'),
    })


def nova(request):
    return formulario(request)


def editar(request, questao_id):
    return formulario(request, get_object_or_404(Questao, id=questao_id))


@require_POST
def excluir(request, questao_id):
    questao = get_object_or_404(Questao, id=questao_id)
    disciplina_id = questao.disciplina_id
    questao.delete()
    messages.success(request, 'Questão excluída.')
    return redirect('questoes:disciplina', disciplina_id=disciplina_id)


# ===== Importar várias de uma vez (ex.: geradas pelo Claude) =====

def importar(request):
    """1º envio: mostra a prévia (o que foi entendido e o que tem problema).
    2º envio ("salvar"): grava as questões que estão certas."""
    previa, problemas, texto = None, [], ''
    disciplina_id, topico_id = ler_id(request.GET.get('disciplina')), ler_id(request.GET.get('topico'))

    if request.method == 'POST':
        form = ImportarForm(request.POST, request.FILES)
        disciplina_id, topico_id = ler_id(request.POST.get('disciplina')), ler_id(request.POST.get('topico'))
        texto = request.POST.get('texto', '')
        if not form.is_valid():
            avisar_erros(request, form)
        else:
            dados = form.cleaned_data
            texto = dados['texto']
            questoes, problemas = ler_questoes(texto)
            if len(questoes) > LIMITE:
                messages.error(request, f'São {len(questoes)} questões: o máximo é {LIMITE} por vez.')
            elif request.POST.get('acao') == 'salvar' and questoes:
                with transaction.atomic():
                    for item in questoes:
                        salvar_questao(Questao(), {**item, 'disciplina': dados['disciplina'], 'topico': dados['topico']})
                total = len(questoes)
                messages.success(request, f'{total} {"questão importada" if total == 1 else "questões importadas"}.')
                return redirect('questoes:disciplina', disciplina_id=dados['disciplina'].id)
            else:
                previa = questoes
                if not questoes:
                    messages.error(request, 'Nenhuma questão encontrada. Confira o formato no exemplo ao lado.')

    return render(request, 'questoes/importar.html', {
        'opcoes': opcoes_de_disciplina(),
        'topicos': topicos_por_disciplina(),
        'disciplina_id': disciplina_id,
        'topico_id': topico_id,
        'texto': texto,
        'previa': previa,
        'problemas': problemas,
        'limite': LIMITE,
    })


# ===== Questionário =====

@require_POST
def criar_questionario(request):
    form = QuestionarioForm(request.POST)
    if not form.is_valid():
        avisar_erros(request, form)
        return redirect('questoes:index')
    dados = form.cleaned_data
    questoes = dados['disciplina'].questoes.all()
    if dados['topico']:
        questoes = questoes.filter(topico=dados['topico'])
    ids = list(questoes.values_list('id', flat=True))
    if not ids:
        messages.error(request, 'Não há questões para esse questionário ainda.')
        return redirect('questoes:disciplina', disciplina_id=dados['disciplina'].id)
    random.shuffle(ids)
    if dados['quantidade']:
        ids = ids[:dados['quantidade']]
    novo = Questionario.objects.create(disciplina=dados['disciplina'], topico=dados['topico'], questoes=ids)
    return redirect('questoes:questionario', questionario_id=novo.id)


def situacao_do_questionario(questionario):
    """(questões na ordem, respostas por questão, a próxima sem resposta ou None).
    Questões excluídas depois de o questionário começar são puladas."""
    existentes = {q.id: q for q in Questao.objects.filter(id__in=questionario.questoes)
                  .select_related('topico').prefetch_related('alternativas')}
    questoes = [existentes[i] for i in questionario.questoes if i in existentes]
    respostas = {r.questao_id: r for r in questionario.respostas.all()}
    proxima = next((q for q in questoes if q.id not in respostas), None)
    return questoes, respostas, proxima


def questionario(request, questionario_id):
    """Uma tela só, em 3 momentos: a pergunta, a correção (?ver=ID da resposta) e o resultado final."""
    item = get_object_or_404(Questionario.objects.select_related('disciplina', 'topico'), id=questionario_id)
    questoes, respostas, proxima = situacao_do_questionario(item)
    contexto = {
        'item': item,
        'total': len(questoes),
        'feitas': len(respostas),
        'certas': sum(r.acertou for r in respostas.values()),
    }

    vista = item.respostas.filter(id=ler_id(request.GET.get('ver'))).select_related('questao').first()
    if vista:
        contexto.update(momento='correcao', questao=next((q for q in questoes if q.id == vista.questao_id), None),
                        resposta=vista, tem_proxima=proxima is not None)
        if contexto['questao']:
            return render(request, 'questoes/questionario.html', contexto)

    if proxima:
        contexto.update(momento='pergunta', questao=proxima, numero=len(respostas) + 1)
        return render(request, 'questoes/questionario.html', contexto)

    # acabou: o resultado, questão por questão
    contexto.update(momento='resultado', linhas=[(q, respostas.get(q.id)) for q in questoes],
                    porcentagem=porcentagem(contexto['certas'], contexto['feitas']),
                    erradas=sum(1 for r in respostas.values() if not r.acertou))
    return render(request, 'questoes/questionario.html', contexto)


@require_POST
def responder(request, questionario_id):
    item = get_object_or_404(Questionario, id=questionario_id)
    questoes, respostas, proxima = situacao_do_questionario(item)
    voltar = redirect('questoes:questionario', questionario_id=item.id)
    # só vale responder a pergunta da vez (evita resposta dobrada com o "voltar" do navegador)
    if not proxima or ler_id(request.POST.get('questao')) != proxima.id:
        return voltar

    if proxima.tipo == 'multipla':
        escolhida = next((a for a in proxima.alternativas.all() if a.id == ler_id(request.POST.get('alternativa'))), None)
        if not escolhida:
            return voltar
        dada, acertou = escolhida.letra, escolhida.correta
    elif proxima.tipo == 'vf':
        dada = request.POST.get('vf')
        if dada not in ('V', 'F'):
            return voltar
        acertou = dada == proxima.resposta
    else:
        # aberta: 1º você escreve e vê a resposta esperada; 2º diz se acertou
        dada = request.POST.get('texto', '').strip()[:5000]
        veredito = request.POST.get('acertou')
        if veredito not in ('sim', 'nao'):
            return render(request, 'questoes/questionario.html', {
                'item': item, 'momento': 'conferir', 'questao': proxima, 'texto': dada,
                'numero': len(respostas) + 1, 'total': len(questoes), 'feitas': len(respostas),
                'certas': sum(r.acertou for r in respostas.values()),
            })
        acertou = veredito == 'sim'

    resposta = Resposta.objects.create(questionario=item, questao=proxima, resposta_dada=dada, acertou=acertou)
    return redirect(reverse('questoes:questionario', args=[item.id]) + f'?ver={resposta.id}')


@require_POST
def refazer_erradas(request, questionario_id):
    """Um questionário novo só com as questões que você errou neste."""
    item = get_object_or_404(Questionario, id=questionario_id)
    erradas = list(item.respostas.filter(acertou=False, questao__isnull=False).values_list('questao_id', flat=True))
    if not erradas:
        return redirect('questoes:questionario', questionario_id=item.id)
    random.shuffle(erradas)
    novo = Questionario.objects.create(disciplina=item.disciplina, topico=item.topico, questoes=erradas)
    return redirect('questoes:questionario', questionario_id=novo.id)
