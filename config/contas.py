"""Conta da Bruna: entrar, sair e trocar a senha.

Usamos as telas prontas do Django (django.contrib.auth); aqui só ajustamos o que muda.
Não existe "criar conta" no site de propósito: num servidor na internet, qualquer pessoa
poderia se cadastrar. A conta é criada no terminal com `manage.py createsuperuser`.
"""
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


class TrocarSenha(auth_views.PasswordChangeView):
    template_name = 'registration/trocar_senha.html'
    success_url = reverse_lazy('dashboard:index')

    def form_valid(self, form):
        # O Django já mantém a pessoa logada depois de trocar a senha; só avisamos.
        resposta = super().form_valid(form)
        messages.success(self.request, 'Senha trocada.')
        return resposta
