import json

from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from estudos.models import Disciplina, Topico
from estudos.views import opcoes_de_disciplina
from projetos.models import Funcionalidade, Projeto
from projetos.views import opcoes_de_projeto

from .models import SessaoPomodoro


def sessoes_de_hoje():
    hoje = timezone.localdate()
    # select_related traz os itens ligados junto, numa consulta só
    return (SessaoPomodoro.objects.filter(concluida_em__date=hoje)
            .select_related('disciplina', 'topico', 'projeto', 'funcionalidade'))


def index(request):
    """Mostra a página do pomodoro com o resumo do dia."""
    sessoes = sessoes_de_hoje()
    # Ex.: [('Ciência da Computação · 2026/2', [Redes 2, ...]), ...]
    opcoes = opcoes_de_disciplina()
    projetos = opcoes_de_projeto()

    # O que aparece na 2ª lista para cada escolha da 1ª:
    #   disciplina "3"  → tópicos dela
    #   projeto   "p:5" → funcionalidades ainda não feitas
    segunda_lista = {
        str(d.id): [{'id': t.id, 'nome': t.nome} for t in d.topicos.all()]
        for _, disciplinas in opcoes for d in disciplinas
    }
    for projeto, funcionalidades in projetos:
        segunda_lista[f'p:{projeto.id}'] = [{'id': f.id, 'nome': f.titulo} for f in funcionalidades]

    # Já vem escolhido quando você chega por "estudar agora" / "trabalhar agora"
    inicial, segunda_inicial = '', ''
    if request.GET.get('disciplina', '') in segunda_lista:
        inicial = request.GET['disciplina']
    elif f"p:{request.GET.get('projeto', '')}" in segunda_lista:
        inicial = f"p:{request.GET['projeto']}"
    elif request.GET.get('topico', '').isdigit():
        topico = Topico.objects.filter(id=request.GET['topico']).first()
        if topico and str(topico.disciplina_id) in segunda_lista:
            inicial, segunda_inicial = str(topico.disciplina_id), topico.id
    elif request.GET.get('funcionalidade', '').isdigit():
        funcionalidade = Funcionalidade.objects.filter(id=request.GET['funcionalidade']).first()
        if funcionalidade and f'p:{funcionalidade.projeto_id}' in segunda_lista:
            inicial, segunda_inicial = f'p:{funcionalidade.projeto_id}', funcionalidade.id

    return render(request, 'pomodoro/index.html', {
        'disciplina_inicial': inicial,
        'segunda_inicial': segunda_inicial,
        'sessoes_hoje': sessoes,
        'minutos_hoje': sessoes.aggregate(total=Sum('duracao_minutos'))['total'] or 0,
        'opcoes': opcoes,
        'projetos': projetos,
        'tem_disciplinas': bool(segunda_lista),
        'topicos_por_disciplina': segunda_lista,
    })


def buscar(modelo, valor, **filtros):
    """Busca pelo id se o valor for um número; senão devolve None."""
    if valor in (None, ''):
        return None
    return modelo.objects.filter(id=int(valor), **filtros).first()


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

    # Tudo opcional. O tópico precisa ser da disciplina; a funcionalidade, do projeto.
    try:
        disciplina = buscar(Disciplina, dados.get('disciplina_id'))
        topico = buscar(Topico, dados.get('topico_id'), disciplina=disciplina) if disciplina else None
        projeto = None if disciplina else buscar(Projeto, dados.get('projeto_id'))
        funcionalidade = (buscar(Funcionalidade, dados.get('funcionalidade_id'), projeto=projeto)
                          if projeto else None)
    except (ValueError, TypeError):
        return JsonResponse({'erro': 'escolha inválida'}, status=400)

    sessao = SessaoPomodoro.objects.create(
        duracao_minutos=minutos,
        disciplina=disciplina,
        topico=topico,
        projeto=projeto,
        funcionalidade=funcionalidade,
        tarefa=str(dados.get('tarefa', ''))[:200],
    )

    principal = disciplina or projeto
    detalhe = topico.nome if topico else (funcionalidade.titulo if funcionalidade else '')
    return JsonResponse({
        'hora': timezone.localtime(sessao.concluida_em).strftime('%H:%M'),
        'duracao_minutos': sessao.duracao_minutos,
        'disciplina': principal.nome if principal else '',
        'topico': detalhe,
        'cor': principal.cor if principal else '',
        'tarefa': sessao.tarefa,
        'minutos_hoje': sessoes_de_hoje().aggregate(total=Sum('duracao_minutos'))['total'] or 0,
    })
