from django.shortcuts import render

from . import calculo


def index(request):
    return render(request, 'desempenho/index.html', {
        'grupos': calculo.pontos_fracos(),
        'janela': calculo.JANELA,
        'minimo': calculo.MINIMO,
        'fraco': calculo.FRACO,
        'bom': calculo.BOM,
    })
