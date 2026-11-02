from datetime import date, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from estudos.models import Categoria, Disciplina

from .models import Evento
from .views import ler_mes


class EventoModelTests(TestCase):
    def test_quando(self):
        hoje = timezone.localdate()
        textos = [Evento(titulo='x', data=hoje + timedelta(days=d)).quando for d in (0, 1, -1, 9, -3)]
        self.assertEqual(textos, ['hoje', 'amanhã', 'ontem', 'em 9 dias', 'há 3 dias'])

    def test_ler_mes(self):
        self.assertEqual(ler_mes('2026-03'), date(2026, 3, 1))
        self.assertEqual(ler_mes('bagunça'), timezone.localdate().replace(day=1))
        self.assertEqual(ler_mes('2026-13'), timezone.localdate().replace(day=1))


class CalendarioTests(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nome='Ciência da Computação', tipo='graduacao')
        self.redes = Disciplina.objects.create(categoria=categoria, nome='Redes 2')
        self.hoje = timezone.localdate()

    def test_pagina_abre_e_navega(self):
        self.assertEqual(self.client.get(reverse('calendario:index')).status_code, 200)
        resposta = self.client.get(reverse('calendario:index') + '?mes=2027-02')
        self.assertContains(resposta, 'fevereiro 2027')

    def test_criar_evento(self):
        resposta = self.client.post(reverse('calendario:criar'), {
            'titulo': 'P1 de Redes', 'tipo': 'prova', 'data': '2026-12-10', 'hora': '19:00',
            'disciplina': self.redes.id, 'descricao': 'camada de enlace',
        })
        evento = Evento.objects.get()
        self.assertEqual((evento.tipo, evento.data, evento.hora, evento.disciplina),
                         ('prova', date(2026, 12, 10), time(19, 0), self.redes))
        self.assertRedirects(resposta, reverse('calendario:index') + '?mes=2026-12')

    def test_evento_sem_hora_nem_disciplina(self):
        self.client.post(reverse('calendario:criar'),
                         {'titulo': 'Entregar relatório', 'tipo': 'entrega', 'data': '2026-12-01'})
        evento = Evento.objects.get()
        self.assertIsNone(evento.hora)
        self.assertIsNone(evento.disciplina)

    def test_sem_titulo_nao_cria(self):
        resposta = self.client.post(reverse('calendario:criar'),
                                    {'titulo': '', 'tipo': 'prova', 'data': '2026-12-01'}, follow=True)
        self.assertFalse(Evento.objects.exists())
        self.assertContains(resposta, 'mensagem error')

    def test_aparece_na_grade_e_nos_proximos(self):
        Evento.objects.create(titulo='Seminário de Redes', tipo='trabalho', data=self.hoje + timedelta(days=2))
        resposta = self.client.get(reverse('calendario:index'))
        self.assertContains(resposta, 'class="evento-chip')  # na grade
        self.assertContains(resposta, 'class="proximo-titulo')  # na lista de próximos
        self.assertContains(resposta, 'em 2 dias')

    def test_editar_evento(self):
        evento = Evento.objects.create(titulo='P1', tipo='prova', data=self.hoje)
        self.assertEqual(self.client.get(reverse('calendario:editar', args=[evento.id])).status_code, 200)
        self.client.post(reverse('calendario:editar', args=[evento.id]),
                         {'titulo': 'P1 de Redes 2', 'tipo': 'prova', 'data': '2026-12-15'})
        evento.refresh_from_db()
        self.assertEqual((evento.titulo, evento.data), ('P1 de Redes 2', date(2026, 12, 15)))

    def test_concluir_some_dos_proximos(self):
        evento = Evento.objects.create(titulo='Lista 3', tipo='entrega', data=self.hoje + timedelta(days=1))
        self.client.post(reverse('calendario:concluir', args=[evento.id]))
        evento.refresh_from_db()
        self.assertTrue(evento.concluido)
        resposta = self.client.get(reverse('calendario:index'))
        self.assertNotIn(evento, list(resposta.context['proximos']))

    def test_proximo_externo_e_ignorado(self):
        evento = Evento.objects.create(titulo='Lista 3', tipo='entrega', data=self.hoje)
        resposta = self.client.post(reverse('calendario:concluir', args=[evento.id]),
                                    {'proximo': 'https://site-malicioso.com/'})
        self.assertTrue(resposta.url.startswith('/calendario/'))

    def test_excluir(self):
        evento = Evento.objects.create(titulo='P1', tipo='prova', data=self.hoje)
        self.client.post(reverse('calendario:excluir', args=[evento.id]))
        self.assertFalse(Evento.objects.exists())

    def test_dashboard_mostra_proximos(self):
        Evento.objects.create(titulo='P2 de Redes', tipo='prova', data=self.hoje + timedelta(days=5))
        resposta = self.client.get(reverse('dashboard:index'))
        self.assertContains(resposta, 'P2 de Redes')
        self.assertContains(resposta, 'marca tipo-prova')
