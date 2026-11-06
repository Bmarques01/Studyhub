from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .contas import TrocarSenha

urlpatterns = [
    path('admin/', admin.site.urls),
    # Conta (as telas de login são as do Django; os templates ficam em templates/registration/)
    path('entrar/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='entrar'),
    path('sair/', auth_views.LogoutView.as_view(), name='sair'),
    path('conta/senha/', TrocarSenha.as_view(), name='trocar_senha'),
    path('pomodoro/', include('pomodoro.urls')),
    path('estudos/', include('estudos.urls')),
    path('calendario/', include('calendario.urls')),
    path('curso/', include('curso.urls')),
    path('projetos/', include('projetos.urls')),
    path('cadernos/', include('cadernos.urls')),
    path('flashcards/', include('flashcards.urls')),
    path('questoes/', include('questoes.urls')),
    path('', include('dashboard.urls')),  # página inicial = dashboard
]
