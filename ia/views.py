from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from estudos.views import avisar_erros, opcoes_de_disciplina
from flashcards.importacao import LIMITE as LIMITE_CARTOES, ler_cartoes
from flashcards.models import Flashcard
from flashcards.views import ler_id
from questoes.importacao import LIMITE as LIMITE_QUESTOES, ler_questoes
from questoes.models import Questao
from questoes.views import salvar_questao, topicos_por_disciplina

from . import gerador
from .forms import GerarForm
from .models import Geracao, custo_do_mes


def gerar(request):
    """O pedido para a IA. Depois de gerar, vai para a revisão (nada é salvo antes dela aprovar)."""
    if request.method == 'POST':
        form = GerarForm(request.POST, request.FILES)
        if not form.is_valid():
            avisar_erros(request, form)
        else:
            dados = form.cleaned_data
            quantidade_questoes = dados['quantidade_questoes'] if dados['gerar_questoes'] else 0
            quantidade_flashcards = dados['quantidade_flashcards'] if dados['gerar_flashcards'] else 0
            try:
                resultado = gerador.gerar(
                    disciplina=dados['disciplina'].nome,
                    topico=dados['topico'].nome if dados['topico'] else '',
                    quantidade_questoes=quantidade_questoes,
                    tipos=dados['tipos'],
                    quantidade_flashcards=quantidade_flashcards,
                    pedido_extra=dados['pedido_extra'],
                    pdf=dados['pdf'],
                    texto=dados['material_texto'],
                )
            except gerador.ErroDaIA as erro:
                messages.error(request, str(erro))
            else:
                # Guardamos mesmo quando deu errado: a API cobrou, e o custo entra no histórico
                geracao = Geracao.objects.create(
                    disciplina=dados['disciplina'], topico=dados['topico'],
                    material=dados['material_nome'], pedido_extra=dados['pedido_extra'],
                    pediu_questoes=quantidade_questoes, pediu_flashcards=quantidade_flashcards,
                    **resultado,
                )
                if geracao.erro:
                    messages.error(request, geracao.erro)
                else:
                    return redirect('ia:revisao', geracao_id=geracao.id)
    else:
        # Vindo do botão de uma disciplina: já chega com ela (e o tópico) escolhidos
        form = GerarForm(initial={
            'disciplina': ler_id(request.GET.get('disciplina')),
            'topico': ler_id(request.GET.get('topico')),
            'gerar_questoes': request.GET.get('so') != 'flashcards',
            'gerar_flashcards': request.GET.get('so') != 'questoes',
        })

    total_mes, geracoes_mes = custo_do_mes()
    return render(request, 'ia/gerar.html', {
        'form': form,
        'opcoes': opcoes_de_disciplina(),
        'topicos': topicos_por_disciplina(),
        'historico': Geracao.objects.select_related('disciplina', 'topico')[:10],
        'total_mes': total_mes,
        'geracoes_mes': geracoes_mes,
    })


def revisao(request, geracao_id):
    """O que a IA gerou, no texto da importação: editar, conferir a prévia e salvar."""
    geracao = get_object_or_404(Geracao.objects.select_related('disciplina', 'topico'), id=geracao_id)
    questoes, problemas_questoes = ler_questoes(geracao.texto_questoes)
    cartoes, problemas_cartoes = ler_cartoes(geracao.texto_flashcards)
    return render(request, 'ia/revisao.html', {
        'geracao': geracao,
        'questoes': questoes,
        'problemas_questoes': problemas_questoes,
        'cartoes': cartoes,
        'problemas_cartoes': problemas_cartoes,
    })


@require_POST
def salvar(request, geracao_id, tipo):
    """acao=previa: só guarda o texto editado (e a página mostra a prévia nova).
    acao=salvar: grava as questões ou os cartões de verdade (uma vez só)."""
    if tipo not in ('questoes', 'flashcards'):
        raise Http404
    geracao = get_object_or_404(Geracao, id=geracao_id)
    if geracao.disciplina is None:
        messages.error(request, 'A disciplina desta geração foi excluída.')
        return redirect('ia:revisao', geracao_id=geracao.id)

    campo_texto, campo_salvos = ('texto_questoes', 'questoes_salvas') if tipo == 'questoes' \
        else ('texto_flashcards', 'flashcards_salvos')
    if getattr(geracao, campo_salvos):
        messages.error(request, 'Esses itens já foram salvos.')
        return redirect('ia:revisao', geracao_id=geracao.id)

    setattr(geracao, campo_texto, request.POST.get('texto', ''))
    if request.POST.get('acao') != 'salvar':
        geracao.save(update_fields=[campo_texto])
        messages.success(request, 'Prévia atualizada.')
        return redirect('ia:revisao', geracao_id=geracao.id)

    with transaction.atomic():
        if tipo == 'questoes':
            itens, _ = ler_questoes(geracao.texto_questoes)
            if len(itens) > LIMITE_QUESTOES:
                itens = []
            for item in itens:
                salvar_questao(Questao(), {**item, 'disciplina': geracao.disciplina, 'topico': geracao.topico})
            nome = 'questão salva' if len(itens) == 1 else 'questões salvas'
        else:
            itens, _ = ler_cartoes(geracao.texto_flashcards)
            if len(itens) > LIMITE_CARTOES:
                itens = []
            Flashcard.objects.bulk_create([
                Flashcard(disciplina=geracao.disciplina, topico=geracao.topico, frente=frente, verso=verso)
                for frente, verso in itens
            ])
            nome = 'flashcard salvo' if len(itens) == 1 else 'flashcards salvos'
        if not itens:
            messages.error(request, 'Não há nada certo para salvar. Confira o texto na prévia.')
            return redirect('ia:revisao', geracao_id=geracao.id)
        setattr(geracao, campo_salvos, len(itens))
        geracao.save(update_fields=[campo_texto, campo_salvos])

    messages.success(request, f'{len(itens)} {nome} em {geracao.disciplina.nome}.')
    return redirect('ia:revisao', geracao_id=geracao.id)

