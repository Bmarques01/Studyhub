"""Base dos testes: o Studyhub exige login em todas as páginas.

Os testes dos apps usam este TestCase em vez do do Django. O cliente dele entra
numa conta de teste sozinho antes da primeira página, então cada teste não
precisa se preocupar com login.
"""
from django.contrib.auth import get_user_model
from django.test import Client
from django.test import TestCase as TestCaseDoDjango


class ClienteLogado(Client):
    def request(self, **request):
        if '_auth_user_id' not in self.session:
            conta, _ = get_user_model().objects.get_or_create(username='teste')
            self.force_login(conta)
        return super().request(**request)


class TestCase(TestCaseDoDjango):
    client_class = ClienteLogado
