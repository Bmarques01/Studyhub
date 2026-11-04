from django.urls import path

from . import views

app_name = 'questoes'

urlpatterns = [
    path('', views.index, name='index'),
    path('disciplina/<int:disciplina_id>/', views.disciplina, name='disciplina'),
    path('nova/', views.nova, name='nova'),
    path('importar/', views.importar, name='importar'),
    path('<int:questao_id>/editar/', views.editar, name='editar'),
    path('<int:questao_id>/excluir/', views.excluir, name='excluir'),

    path('questionario/novo/', views.criar_questionario, name='criar_questionario'),
    path('questionario/<int:questionario_id>/', views.questionario, name='questionario'),
    path('questionario/<int:questionario_id>/responder/', views.responder, name='responder'),
    path('questionario/<int:questionario_id>/refazer/', views.refazer_erradas, name='refazer_erradas'),
]
