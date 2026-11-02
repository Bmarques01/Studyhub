import json

from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from estudos.models import Disciplina, Topico
from estudos.views import avisar_erros, opcoes_de_disciplina

from .forms import CadernoForm, NovoCadernoForm
from .models import Caderno, Pagina

TAMANHO_MAXIMO = 2_000_000  # ~2 MB de conteúdo por página


def index(request):
    cadernos = (Caderno.objects.select_related('disciplina')
                .annotate(total_paginas=Count('paginas')).order_by('-atualizado_em'))
    filtro = None
    pedida = request.GET.get('disciplina', '')
    if pedida.isdigit():
        filtro = Disciplina.objects.filter(id=pedida).first()
        if filtro:
            cadernos = cadernos.filter(disciplina=filtro)
    return render(request, 'cadernos/index.html', {
        'cadernos': cadernos,
        'filtro': filtro,
        'opcoes': opcoes_de_disciplina(),
    })


@require_POST
def criar_caderno(request):
    form = NovoCadernoForm(request.POST)
    if not form.is_valid():
        avisar_erros(request, form)
        return redirect('cadernos:index')
    caderno = form.save()
    pagina = Pagina.objects.create(caderno=caderno, titulo='Primeira página')
    return redirect('cadernos:pagina', pagina_id=pagina.id)


def caderno(request, caderno_id):
    """Abrir um caderno = abrir a página mais recente dele (ou mostrar o caderno vazio)."""
    item = get_object_or_404(Caderno, id=caderno_id)
    pagina = item.paginas.order_by('-atualizada_em').first()
    if pagina:
        return redirect('cadernos:pagina', pagina_id=pagina.id)
    return render(request, 'cadernos/pagina.html', contexto_do_caderno(item, None))


def contexto_do_caderno(item, pagina):
    return {
        'caderno': item,
        'pagina': pagina,
        'paginas': item.paginas.only('id', 'titulo', 'atualizada_em', 'criada_em'),
        'topicos': item.disciplina.topicos.all() if item.disciplina else [],
        'form': CadernoForm(instance=item),
        'papeis': Caderno.PAPEIS,
        'fontes': Caderno.FONTES,
        'opcoes': opcoes_de_disciplina(),
    }


def pagina(request, pagina_id):
    item = get_object_or_404(Pagina.objects.select_related('caderno__disciplina', 'topico'), id=pagina_id)
    return render(request, 'cadernos/pagina.html', contexto_do_caderno(item.caderno, item))


@require_POST
def criar_pagina(request, caderno_id):
    item = get_object_or_404(Caderno, id=caderno_id)
    nova = Pagina.objects.create(caderno=item, titulo='Nova página')
    item.save(update_fields=['atualizado_em'])
    return redirect('cadernos:pagina', pagina_id=nova.id)


@require_POST
def salvar_pagina(request, pagina_id):
    """Salvamento automático: o editor manda título, conteúdo e tópico enquanto você escreve."""
    item = get_object_or_404(Pagina.objects.select_related('caderno'), id=pagina_id)
    if len(request.body) > TAMANHO_MAXIMO:
        return JsonResponse({'erro': 'Página grande demais para salvar.'}, status=413)
    try:
        dados = json.loads(request.body)
    except ValueError:
        return JsonResponse({'erro': 'dados inválidos'}, status=400)

    conteudo = dados.get('conteudo')
    if conteudo is not None:
        if not (isinstance(conteudo, dict) and isinstance(conteudo.get('ops'), list)):
            return JsonResponse({'erro': 'conteúdo inválido'}, status=400)
        item.conteudo = conteudo
        item.texto = str(dados.get('texto', ''))[:200_000]
    if 'titulo' in dados:
        item.titulo = str(dados['titulo']).strip()[:150] or 'Sem título'
    if 'topico_id' in dados:
        # o tópico precisa ser da disciplina do caderno
        topico_id = dados['topico_id']
        item.topico = (Topico.objects.filter(id=topico_id, disciplina_id=item.caderno.disciplina_id).first()
                       if str(topico_id).isdigit() else None)

    item.save()
    item.caderno.save(update_fields=['atualizado_em'])
    return JsonResponse({'ok': True, 'salvo_em': timezone.localtime(item.atualizada_em).strftime('%H:%M')})


@require_POST
def excluir_pagina(request, pagina_id):
    item = get_object_or_404(Pagina, id=pagina_id)
    caderno_id = item.caderno_id
    item.delete()
    messages.success(request, f'Página "{item.titulo}" excluída.')
    return redirect('cadernos:caderno', caderno_id=caderno_id)


@require_POST
def editar_caderno(request, caderno_id):
    item = get_object_or_404(Caderno, id=caderno_id)
    form = CadernoForm(request.POST, instance=item)
    if form.is_valid():
        form.save()
    else:
        avisar_erros(request, form)
    return redirect('cadernos:caderno', caderno_id=item.id)


@require_POST
def excluir_caderno(request, caderno_id):
    item = get_object_or_404(Caderno, id=caderno_id)
    item.delete()
    messages.success(request, f'Caderno "{item.nome}" excluído.')
    return redirect('cadernos:index')
