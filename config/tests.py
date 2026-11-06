from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class LoginTests(TestCase):
    """Aqui o cliente é o normal do Django (sem login automático)."""

    def setUp(self):
        self.conta = get_user_model().objects.create_user('bruna', password='senha-forte-123')

    def test_sem_login_vai_para_a_tela_de_entrar(self):
        for url in [reverse('dashboard:index'), reverse('questoes:index'), reverse('pomodoro:index')]:
            resposta = self.client.get(url)
            self.assertRedirects(resposta, f"{reverse('entrar')}?next={url}", fetch_redirect_response=False)
        # O registro do pomodoro (JSON) também fica fechado
        resposta = self.client.post(reverse('pomodoro:registrar'), '{}', content_type='application/json')
        self.assertEqual(resposta.status_code, 302)

    def test_tela_de_entrar_nao_mostra_o_menu(self):
        resposta = self.client.get(reverse('entrar'))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, 'class="menu"')

    def test_entrar_e_voltar_para_a_pagina_pedida(self):
        resposta = self.client.post(reverse('entrar'), {
            'username': 'bruna', 'password': 'senha-forte-123', 'next': reverse('questoes:index')})
        self.assertRedirects(resposta, reverse('questoes:index'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('dashboard:index')).status_code, 200)

    def test_senha_errada(self):
        resposta = self.client.post(reverse('entrar'), {'username': 'bruna', 'password': 'errada'})
        self.assertContains(resposta, 'Usuário ou senha incorretos')

    def test_next_de_fora_e_ignorado(self):
        resposta = self.client.post(reverse('entrar'), {
            'username': 'bruna', 'password': 'senha-forte-123', 'next': 'https://site-malicioso.com/'})
        self.assertRedirects(resposta, reverse('dashboard:index'), fetch_redirect_response=False)

    def test_menu_mostra_o_nome_e_sair_desloga(self):
        self.client.force_login(self.conta)
        self.assertContains(self.client.get(reverse('dashboard:index')), '<strong>bruna</strong>', html=True)
        # Sair só por POST
        self.assertEqual(self.client.get(reverse('sair')).status_code, 405)
        self.assertRedirects(self.client.post(reverse('sair')), reverse('entrar'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('dashboard:index')).status_code, 302)

    def test_trocar_senha(self):
        self.client.force_login(self.conta)
        url = reverse('trocar_senha')
        resposta = self.client.post(url, {'old_password': 'errada', 'new_password1': 'outra-senha-456',
                                          'new_password2': 'outra-senha-456'})
        self.assertEqual(resposta.status_code, 200)  # senha atual errada: fica na página
        resposta = self.client.post(url, {'old_password': 'senha-forte-123', 'new_password1': 'outra-senha-456',
                                          'new_password2': 'outra-senha-456'}, follow=True)
        self.assertContains(resposta, 'Senha trocada.')
        self.conta.refresh_from_db()
        self.assertTrue(self.conta.check_password('outra-senha-456'))
