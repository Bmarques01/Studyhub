from django.urls import path

from . import views

app_name = 'estudos'

urlpatterns = [
    path('', views.index, name='index'),

    path('categorias/nova/', views.criar_categoria, name='criar_categoria'),
    path('categorias/<int:categoria_id>/editar/', views.editar_categoria, name='editar_categoria'),
    path('categorias/<int:categoria_id>/excluir/', views.excluir_categoria, name='excluir_categoria'),

    path('categorias/<int:categoria_id>/periodos/novo/', views.criar_periodo, name='criar_periodo'),
    path('periodos/<int:periodo_id>/editar/', views.editar_periodo, name='editar_periodo'),
    path('periodos/<int:periodo_id>/excluir/', views.excluir_periodo, name='excluir_periodo'),

    path('disciplinas/nova/', views.criar_disciplina, name='criar_disciplina'),
    path('disciplinas/<int:disciplina_id>/editar/', views.editar_disciplina, name='editar_disciplina'),
    path('disciplinas/<int:disciplina_id>/arquivar/', views.arquivar_disciplina, name='arquivar_disciplina'),
    path('disciplinas/<int:disciplina_id>/excluir/', views.excluir_disciplina, name='excluir_disciplina'),

    path('disciplinas/<int:disciplina_id>/topicos/novo/', views.criar_topico, name='criar_topico'),
    path('topicos/<int:topico_id>/editar/', views.editar_topico, name='editar_topico'),
    path('topicos/<int:topico_id>/excluir/', views.excluir_topico, name='excluir_topico'),
]
