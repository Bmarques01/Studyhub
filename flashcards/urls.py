from django.urls import path

from . import views

app_name = 'flashcards'

urlpatterns = [
    path('', views.index, name='index'),
    path('disciplina/<int:disciplina_id>/', views.disciplina, name='disciplina'),
    path('novo/', views.criar, name='criar'),
    path('baralho/novo/', views.criar_baralho, name='criar_baralho'),
    path('importar/', views.importar, name='importar'),
    path('limite/', views.salvar_limite, name='salvar_limite'),
    path('<int:cartao_id>/editar/', views.editar, name='editar'),
    path('<int:cartao_id>/excluir/', views.excluir, name='excluir'),

    path('revisar/', views.revisar, name='revisar'),
    path('revisar/proximo/', views.proximo, name='proximo'),
    path('<int:cartao_id>/responder/', views.responder, name='responder'),
]
