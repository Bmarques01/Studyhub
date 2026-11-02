from django.urls import path

from . import views

app_name = 'pomodoro'

urlpatterns = [
    path('', views.index, name='index'),
    path('registrar/', views.registrar_sessao, name='registrar'),
]
