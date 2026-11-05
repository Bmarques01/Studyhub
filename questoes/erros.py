"""Caderno de erros: as questões que você errou, até marcar "dominei".

Os erros entram sozinhos quando você erra no questionário (ver `responder` em views.py)
ou pelo "+ erro" (questões de provas e listas feitas fora do Studyhub).
"""
import random
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from estudos.models import Disciplina
from estudos.views import avisar_erros, opcoes_de_disciplina
from flashcards.views import ler_id

from .forms import AnotarErroForm, ErroDeForaForm
from .models import Erro, Questao, Questionario
from .views import salvar_questao, topicos_por_disciplina


def voltar_para(request, padrao):
    """Volta para a página de onde o formulário veio (campo "proximo"), se for deste site."""
    proximo = request.POST.get('proximo', '')
    if url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
        return redirect(proximo)
    return redirect(padrao)


def link_dos_erros(disciplina_id=None, erro_id=None):
    url = reverse('questoes:erros')
    if disciplina_id:
        url += f'?disciplina={disciplina_id}'
    return url + (f'#erro-{erro_id}' if erro_id else '')


# ===== A página do caderno de erros =====

def erros(request):
    disciplina = Disciplina.objects.filter(id=ler_id(request.GET.get('disciplina'))).first()
    ver_dominados = request.GET.get('dominados') == '1'

    todos = Erro.objects.select_related('questao__disciplina', 'questao__topico').prefetch_related('questao__alternativas')
    pendentes = todos.filter(dominado_em__isnull=True)
    dominados = todos.filter(dominado_em__isnull=False)

    # filtro: uma caixinha por disciplina que tem erros para revisar
    por_disciplina = dict(pendentes.values_list('questao__disciplina').annotate(n=Count('id')).order_by())
    filtros = [(d, por_disciplina[d.id]) for d in Disciplina.objects.filter(id__in=por_disciplina).order_by('nome')]

    lista = dominados.order_by('-dominado_em', '-id') if ver_dominados else pendentes
    if disciplina:
        lista = lista.filter(questao__disciplina=disciplina)
        dominados = dominados.filter(questao__disciplina=disciplina)

    # agrupados por disciplina (cada grupo tem o botão "revisar")
    grupos = {}
    for erro in lista:
        d = erro.questao.disciplina
        grupos.setdefault(d.id, {'disciplina': d, 'erros': []})['erros'].append(erro)
    grupos = sorted(grupos.values(), key=lambda g: g['disciplina'].nome.lower())

    # com uma disciplina escolhida: os tópicos em que você mais erra e os motivos
    topicos_mais_errados, motivos = [], []
    if disciplina and not ver_dominados:
        linhas = (pendentes.filter(questao__disciplina=disciplina)
                  .values('questao__topico', 'questao__topico__nome')
                  .annotate(questoes=Count('id'), vezes=Sum('vezes')).order_by('-vezes', '-questoes'))
        topicos_mais_errados = [
            {'id': linha['questao__topico'], 'nome': linha['questao__topico__nome'] or 'sem tópico',
             'questoes': linha['questoes'], 'vezes': linha['vezes']}
            for linha in linhas[:6]
        ]
        contagem = dict(pendentes.filter(questao__disciplina=disciplina)
                        .values_list('motivo').annotate(n=Count('id')).order_by())
        motivos = [(texto, contagem[valor]) for valor, texto in Erro.MOTIVOS if contagem.get(valor)]
        if contagem.get(''):
            motivos.append(('sem motivo ainda', contagem['']))

    return render(request, 'questoes/erros.html', {
        'disciplina': disciplina,
        'ver_dominados': ver_dominados,
        'grupos': grupos,
        'filtros': filtros,
        'total_pendentes': sum(por_disciplina.values()),
        'total_dominados': dominados.count(),
        'topicos_mais_errados': topicos_mais_errados,
        'maior': topicos_mais_errados[0]['vezes'] if topicos_mais_errados else 0,
        'motivos': motivos,
        'motivos_opcoes': Erro.MOTIVOS,
    })


# ===== Por que errei / anotação / dominei =====

@require_POST
def salvar_erro(request, erro_id):
    """Guarda o "por que errei" e a anotação. Só mexe no que veio no formulário."""
    erro = get_object_or_404(Erro.objects.select_related('questao'), id=erro_id)
    form = AnotarErroForm(request.POST)
    if not form.is_valid():
        avisar_erros(request, form)
    else:
        if 'motivo' in request.POST:
            erro.motivo = form.cleaned_data['motivo']
        if 'anotacao' in request.POST:
            erro.anotacao = form.cleaned_data['anotacao'].strip()
        erro.save(update_fields=['motivo', 'anotacao'])
    return voltar_para(request, link_dos_erros(erro.questao.disciplina_id, erro.id))


@require_POST
def dominei(request, erro_id):
    """Tira o erro da lista ("dominei") ou devolve para ela ("voltar para os erros")."""
    erro = get_object_or_404(Erro.objects.select_related('questao'), id=erro_id)
    if request.POST.get('acao') == 'voltar':
        erro.dominado_em = None
        messages.success(request, 'A questão voltou para o caderno de erros.')
    else:
        erro.dominado_em = timezone.now()
        messages.success(request, 'Dominada! Saiu do caderno de erros.')
    erro.save(update_fields=['dominado_em'])
    return voltar_para(request, link_dos_erros(erro.questao.disciplina_id))


# ===== Revisar: um questionário só com os erros =====

@require_POST
def revisar(request):
    disciplina = get_object_or_404(Disciplina, id=ler_id(request.POST.get('disciplina')))
    erros = Erro.objects.filter(dominado_em__isnull=True, questao__disciplina=disciplina)
    topico = request.POST.get('topico')  # opcional: só um tópico ("sem" = as sem tópico)
    if topico == 'sem':
        erros = erros.filter(questao__topico=None)
    elif ler_id(topico):
        erros = erros.filter(questao__topico_id=ler_id(topico))
    ids = list(erros.values_list('questao_id', flat=True))
    if not ids:
        messages.error(request, 'Nenhum erro para revisar aqui.')
        return redirect(link_dos_erros(disciplina.id))
    random.shuffle(ids)
    novo = Questionario.objects.create(disciplina=disciplina, questoes=ids, de_erros=True,
                                       sem_topico=topico == 'sem')
    if ler_id(topico):
        novo.topicos.set(disciplina.topicos.filter(id=ler_id(topico)))
    return redirect('questoes:questionario', questionario_id=novo.id)


# ===== "+ erro": questão errada fora do Studyhub =====

def novo(request):
    if request.method == 'POST':
        form = ErroDeForaForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            # vira uma questão aberta no banco (dá para praticar depois) e já entra no caderno
            questao = salvar_questao(Questao(), {
                'disciplina': dados['disciplina'], 'topico': dados['topico'], 'tipo': 'aberta',
                'enunciado': dados['enunciado'], 'resposta': dados['resposta_certa'].strip(),
                'explicacao': dados['explicacao'],
            })
            erro = Erro.objects.create(
                questao=questao, origem=dados['origem'].strip() or 'fora do Studyhub',
                resposta_dada=dados['resposta_dada'].strip(), motivo=dados['motivo'],
                anotacao=dados['anotacao'].strip())
            if 'outro' in request.POST:
                # "salvar e anotar outro": volta com a mesma disciplina, tópico e origem (ex.: a mesma prova)
                messages.success(request, 'Erro anotado. Pode anotar o próximo.')
                campos = {'disciplina': dados['disciplina'].id, 'topico': dados['topico'].id if dados['topico'] else '',
                          'origem': dados['origem'].strip()}
                return redirect(reverse('questoes:novo_erro') + '?' + urlencode(campos))
            messages.success(request, 'Erro anotado no caderno.')
            return redirect(link_dos_erros(dados['disciplina'].id, erro.id))
        valores = request.POST
        erros_do_form = [erro for lista in form.errors.values() for erro in lista]
    else:
        valores = request.GET
        erros_do_form = []

    disciplina_id = ler_id(valores.get('disciplina'))
    return render(request, 'questoes/erro_form.html', {
        'valores': valores,
        'disciplina_id': disciplina_id,
        'topico_id': ler_id(valores.get('topico')) or '',
        'erros': erros_do_form,
        'opcoes': opcoes_de_disciplina(),
        'topicos': topicos_por_disciplina(),
        'motivos_opcoes': Erro.MOTIVOS,
        'voltar': link_dos_erros(disciplina_id if Disciplina.objects.filter(id=disciplina_id).exists() else None),
    })

