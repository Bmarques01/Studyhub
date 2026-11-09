from django.urls import path

from . import erros, views

app_name = 'questoes'

urlpatterns = [
    path('', views.index, name='index'),
    path('disciplina/<int:disciplina_id>/', views.disciplina, name='disciplina'),
    path('disciplina/nova/', views.nova_disciplina, name='nova_disciplina'),
    path('nova/', views.nova, name='nova'),
    path('importar/', views.importar, name='importar'),
    path('<int:questao_id>/editar/', views.editar, name='editar'),
    path('<int:questao_id>/excluir/', views.excluir, name='excluir'),

    path('questionario/novo/', views.criar_questionario, name='criar_questionario'),
    path('questionario/<int:questionario_id>/', views.questionario, name='questionario'),
    path('questionario/<int:questionario_id>/responder/', views.responder, name='responder'),
    path('questionario/<int:questionario_id>/desfazer/<int:resposta_id>/', views.desfazer, name='desfazer'),
    path('questionario/<int:questionario_id>/refazer/', views.refazer_erradas, name='refazer_erradas'),

    # caderno de erros (os nomes têm "erro": é assim que o menu sabe marcar "Erros")
    path('erros/', erros.erros, name='erros'),
    path('erros/novo/', erros.novo, name='novo_erro'),
    path('erros/revisar/', erros.revisar, name='revisar_erros'),
    path('erros/<int:erro_id>/', erros.salvar_erro, name='salvar_erro'),
    path('erros/<int:erro_id>/dominei/', erros.dominei, name='erro_dominei'),
]
