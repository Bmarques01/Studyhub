from django.urls import path

from . import views

app_name = 'curso'

urlpatterns = [
    path('', views.index, name='index'),
    path('<int:disciplina_id>/situacao/', views.mudar_situacao, name='situacao'),
]
