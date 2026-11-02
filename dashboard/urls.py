from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('meta/', views.salvar_meta, name='salvar_meta'),
]
