from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from estudos.models import Categoria, Disciplina
from pomodoro.models import SessaoPomodoro

from .models import Perfil
from .templatetags.tempo import horas
from .views import comparacao, escala, nivel_do_dia, sequencia_de_dias


def criar_sessao(minutos, dias_atras=0, disciplina=None):
    """Cria uma sessão e "volta no tempo" a data dela."""
    sessao = SessaoPomodoro.objects.create(duracao_minutos=minutos, disciplina=disciplina)
    momento = timezone.now() - timedelta(days=dias_atras)
    SessaoPomodoro.objects.filter(id=sessao.id).update(concluida_em=momento)
    return sessao


class FuncoesTests(TestCase):
    def test_horas(self):
        self.assertEqual(horas(0), '0min')
        self.assertEqual(horas(45), '45min')
        self.assertEqual(horas(60), '1h')
        self.assertEqual(horas(80), '1h20')
        self.assertEqual(horas(125), '2h05')

    def test_sequencia(self):
        hoje = timezone.localdate()
        d = lambda n: hoje - timedelta(days=n)
        self.assertEqual(sequencia_de_dias({d(0): 25, d(1): 25, d(2): 25, d(4): 25}, hoje), 3)
        # hoje ainda sem estudo: a sequência de ontem continua valendo
        self.assertEqual(sequencia_de_dias({d(1): 25, d(2): 25}, hoje), 2)
        self.assertEqual(sequencia_de_dias({d(2): 25}, hoje), 0)

    def test_comparacao(self):
        self.assertEqual(comparacao(90, 30), {'texto': '+1h', 'direcao': 'subiu'})
        self.assertEqual(comparacao(30, 75), {'texto': '−45min', 'direcao': 'desceu'})
        self.assertEqual(comparacao(0, 0)['direcao'], 'igual')

    def test_escala_e_niveis(self):
        self.assertEqual(escala(0), 60)
        self.assertEqual(escala(61), 120)
        self.assertEqual([nivel_do_dia(m) for m in (0, 10, 45, 90, 200)], [0, 1, 2, 3, 4])


class DashboardTests(TestCase):
    def test_pagina_vazia_abre(self):
        resposta = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Bruna')
        self.assertContains(resposta, 'Nenhum pomodoro este mês ainda')

    def test_mostra_totais_e_disciplinas(self):
        categoria = Categoria.objects.create(nome='Cloud Computing')
        k8s = Disciplina.objects.create(categoria=categoria, nome='Kubernetes', cor='#a77bf3')
        criar_sessao(50, disciplina=k8s)
        criar_sessao(25)

        resposta = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resposta.context['cards'][0]['minutos'], 75)  # hoje
        self.assertContains(resposta, 'Kubernetes')
        self.assertContains(resposta, 'Sem disciplina')
        self.assertEqual(resposta.context['sequencia'], 1)

    def test_salvar_meta(self):
        self.client.post(reverse('dashboard:salvar_meta'), {'meta_semanal_horas': '15'})
        self.assertEqual(Perfil.atual().meta_semanal_horas, 15)

        self.client.post(reverse('dashboard:salvar_meta'), {'meta_semanal_horas': '0'})  # inválido
        self.client.post(reverse('dashboard:salvar_meta'), {'meta_semanal_horas': 'abc'})  # inválido
        self.assertEqual(Perfil.atual().meta_semanal_horas, 15)

    def test_porcentagem_da_meta(self):
        Perfil.objects.create(pk=1, meta_semanal_horas=1)
        criar_sessao(30)
        resposta = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resposta.context['meta_pct'], 50)


class BackupTests(TestCase):
    def test_backup_gera_arquivo_que_restaura(self):
        import io
        import json
        import tempfile
        from pathlib import Path

        from django.core.management import call_command
        from django.test import override_settings

        Perfil.objects.create(pk=1, meta_semanal_horas=12)
        SessaoPomodoro.objects.create(duracao_minutos=25)
        with tempfile.TemporaryDirectory() as pasta, override_settings(BASE_DIR=Path(pasta)):
            call_command('fazer_backup', stdout=io.StringIO())
            arquivo = next((Path(pasta) / 'backup').glob('studyhub-*.json'))
            dados = json.loads(arquivo.read_text(encoding='utf-8'))
            modelos = {item['model'] for item in dados}
            self.assertIn('dashboard.perfil', modelos)
            self.assertIn('pomodoro.sessaopomodoro', modelos)
            # restaura num banco "limpo"
            SessaoPomodoro.objects.all().delete()
            Perfil.objects.all().delete()
            call_command('loaddata', str(arquivo), verbosity=0)
        self.assertEqual(Perfil.atual().meta_semanal_horas, 12)
        self.assertEqual(SessaoPomodoro.objects.count(), 1)
