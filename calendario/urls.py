from django.urls import path

from . import views

app_name = 'calendario'

urlpatterns = [
    path('', views.index, name='index'),
    path('novo/', views.criar, name='criar'),
    path('<int:evento_id>/editar/', views.editar, name='editar'),
    path('<int:evento_id>/excluir/', views.excluir, name='excluir'),
    path('<int:evento_id>/concluir/', views.alternar_concluido, name='concluir'),
]
