import json

from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from estudos.models import Disciplina, Topico
from estudos.views import opcoes_de_disciplina

from .models import SessaoPomodoro


def sessoes_de_hoje():
    hoje = timezone.localdate()
    # select_related traz disciplina e tópico junto, numa consulta só
    return SessaoPomodoro.objects.filter(concluida_em__date=hoje).select_related('disciplina', 'topico')


def index(request):
    """Mostra a página do pomodoro com o resumo do dia."""
    sessoes = sessoes_de_hoje()
    # Ex.: [('Ciência da Computação · 5º semestre', [Redes 2, ...]), ...]
    opcoes = opcoes_de_disciplina()

    # Tópicos de cada disciplina, para o JavaScript preencher a 2ª lista de escolha
    topicos_por_disciplina = {
        d.id: [{'id': t.id, 'nome': t.nome} for t in d.topicos.all()]
        for _, disciplinas in opcoes for d in disciplinas
    }

    return render(request, 'pomodoro/index.html', {
        'sessoes_hoje': sessoes,
        'minutos_hoje': sessoes.aggregate(total=Sum('duracao_minutos'))['total'] or 0,
        'opcoes': opcoes,
        'tem_disciplinas': bool(topicos_por_disciplina),
        'topicos_por_disciplina': topicos_por_disciplina,
    })


@require_POST
def registrar_sessao(request):
    """Chamada pelo JavaScript quando um bloco de foco termina. Salva no banco."""
    try:
        dados = json.loads(request.body)
        minutos = int(dados['duracao_minutos'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'erro': 'dados inválidos'}, status=400)

    if not 1 <= minutos <= 180:
        return JsonResponse({'erro': 'duração inválida'}, status=400)

    # Disciplina e tópico são opcionais. O tópico precisa ser da disciplina escolhida.
    disciplina = None
    topico = None
    try:
        if dados.get('disciplina_id'):
            disciplina = Disciplina.objects.filter(id=int(dados['disciplina_id'])).first()
        if disciplina and dados.get('topico_id'):
            topico = Topico.objects.filter(id=int(dados['topico_id']), disciplina=disciplina).first()
    except (ValueError, TypeError):
        return JsonResponse({'erro': 'disciplina ou tópico inválido'}, status=400)

    sessao = SessaoPomodoro.objects.create(
        duracao_minutos=minutos,
        disciplina=disciplina,
        topico=topico,
        tarefa=str(dados.get('tarefa', ''))[:200],
    )

    return JsonResponse({
        'hora': timezone.localtime(sessao.concluida_em).strftime('%H:%M'),
        'duracao_minutos': sessao.duracao_minutos,
        'disciplina': disciplina.nome if disciplina else '',
        'topico': topico.nome if topico else '',
        'cor': disciplina.cor if disciplina else '',
        'tarefa': sessao.tarefa,
        'minutos_hoje': sessoes_de_hoje().aggregate(total=Sum('duracao_minutos'))['total'] or 0,
    })
