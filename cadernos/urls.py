from django.urls import path

from . import views

app_name = 'cadernos'

urlpatterns = [
    path('', views.index, name='index'),
    path('novo/', views.criar_caderno, name='criar_caderno'),
    path('<int:caderno_id>/', views.caderno, name='caderno'),
    path('<int:caderno_id>/editar/', views.editar_caderno, name='editar_caderno'),
    path('<int:caderno_id>/excluir/', views.excluir_caderno, name='excluir_caderno'),
    path('<int:caderno_id>/paginas/nova/', views.criar_pagina, name='criar_pagina'),
    path('paginas/<int:pagina_id>/', views.pagina, name='pagina'),
    path('paginas/<int:pagina_id>/salvar/', views.salvar_pagina, name='salvar_pagina'),
    path('paginas/<int:pagina_id>/excluir/', views.excluir_pagina, name='excluir_pagina'),
]
