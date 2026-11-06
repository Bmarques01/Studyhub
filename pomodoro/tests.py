import json

from config.testes import TestCase
from django.urls import reverse

from estudos.models import Categoria, Disciplina, Topico

from .models import SessaoPomodoro


class PomodoroTests(TestCase):
    def test_pagina_abre(self):
        resposta = self.client.get(reverse('pomodoro:index'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Nenhum pomodoro ainda')

    def test_controles_do_ruido(self):
        # na página do pomodoro: ligar, os 3 tipos e o volume
        resposta = self.client.get(reverse('pomodoro:index'))
        self.assertContains(resposta, 'id="ruido-ligar"')
        for tipo in ('branco', 'rosa', 'marrom'):
            self.assertContains(resposta, f'data-ruido-tipo="{tipo}"')
        self.assertContains(resposta, 'id="ruido-volume"')
        # nas outras páginas: o botão no mini pomodoro
        self.assertContains(self.client.get(reverse('calendario:index')), 'id="mini-ruido"')

    def test_registrar_sessao(self):
        resposta = self.client.post(
            reverse('pomodoro:registrar'),
            data=json.dumps({'duracao_minutos': 25, 'tarefa': 'Anatomia'}),
            content_type='application/json',
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['minutos_hoje'], 25)
        self.assertEqual(SessaoPomodoro.objects.get().tarefa, 'Anatomia')

        # A sessão aparece na página
        self.assertContains(self.client.get(reverse('pomodoro:index')), 'Anatomia')

    def test_registrar_com_disciplina_e_topico(self):
        categoria = Categoria.objects.create(nome="Cloud Computing", tipo="pos")
        k8s = Disciplina.objects.create(categoria=categoria, nome='Kubernetes', cor='#a77bf3')
        topico = Topico.objects.create(disciplina=k8s, nome='Deployments')

        resposta = self.client.post(
            reverse('pomodoro:registrar'),
            data=json.dumps({'duracao_minutos': 25, 'disciplina_id': k8s.id, 'topico_id': topico.id}),
            content_type='application/json',
        )
        self.assertEqual(resposta.json()['disciplina'], 'Kubernetes')
        sessao = SessaoPomodoro.objects.get()
        self.assertEqual(sessao.disciplina, k8s)
        self.assertEqual(sessao.topico, topico)

    def test_topico_de_outra_disciplina_e_ignorado(self):
        categoria = Categoria.objects.create(nome="Cloud Computing", tipo="pos")
        k8s = Disciplina.objects.create(categoria=categoria, nome='Kubernetes')
        aws = Disciplina.objects.create(categoria=categoria, nome='AWS')
        topico_aws = Topico.objects.create(disciplina=aws, nome='VPC')

        self.client.post(
            reverse('pomodoro:registrar'),
            data=json.dumps({'duracao_minutos': 25, 'disciplina_id': k8s.id, 'topico_id': topico_aws.id}),
            content_type='application/json',
        )
        self.assertIsNone(SessaoPomodoro.objects.get().topico)

    def test_excluir_disciplina_mantem_sessao(self):
        categoria = Categoria.objects.create(nome="Cloud Computing", tipo="pos")
        k8s = Disciplina.objects.create(categoria=categoria, nome='Kubernetes')
        SessaoPomodoro.objects.create(duracao_minutos=25, disciplina=k8s)
        k8s.delete()
        self.assertIsNone(SessaoPomodoro.objects.get().disciplina)

    def test_rejeita_duracao_invalida(self):
        resposta = self.client.post(
            reverse('pomodoro:registrar'),
            data=json.dumps({'duracao_minutos': 0}),
            content_type='application/json',
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(SessaoPomodoro.objects.exists())
