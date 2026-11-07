from django.urls import path

from . import views

app_name = 'ia'

urlpatterns = [
    path('gerar/', views.gerar, name='gerar'),
    path('gerar/<int:geracao_id>/', views.revisao, name='revisao'),
    path('gerar/<int:geracao_id>/<str:tipo>/', views.salvar, name='salvar'),
    path('resumo/<int:caderno_id>/', views.resumo, name='resumo'),
]
