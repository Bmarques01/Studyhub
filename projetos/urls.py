from django.urls import path

from . import views

app_name = 'projetos'

urlpatterns = [
    path('', views.index, name='index'),
    path('novo/', views.criar_projeto, name='criar_projeto'),
    path('<int:projeto_id>/', views.projeto, name='projeto'),
    path('<int:projeto_id>/editar/', views.editar_projeto, name='editar_projeto'),
    path('<int:projeto_id>/excluir/', views.excluir_projeto, name='excluir_projeto'),
    path('<int:projeto_id>/funcionalidades/nova/', views.criar_funcionalidade, name='criar_funcionalidade'),
    path('<int:projeto_id>/diario/novo/', views.criar_entrada, name='criar_entrada'),

    path('funcionalidades/<int:funcionalidade_id>/', views.funcionalidade, name='funcionalidade'),
    path('funcionalidades/<int:funcionalidade_id>/mover/', views.mover_funcionalidade, name='mover'),
    path('funcionalidades/<int:funcionalidade_id>/excluir/', views.excluir_funcionalidade,
         name='excluir_funcionalidade'),
    path('funcionalidades/<int:funcionalidade_id>/tarefas/nova/', views.criar_tarefa, name='criar_tarefa'),

    path('tarefas/<int:tarefa_id>/alternar/', views.alternar_tarefa, name='alternar_tarefa'),
    path('tarefas/<int:tarefa_id>/excluir/', views.excluir_tarefa, name='excluir_tarefa'),
    path('diario/<int:entrada_id>/excluir/', views.excluir_entrada, name='excluir_entrada'),
]
