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
        self.assertContains(resposta, 'Nenhum pomodoro esta semana')  # filtro padrão

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


class PeriodoTests(TestCase):
    """O filtro do dashboard: datas de cada período e o que muda na página."""

    def test_datas_dos_periodos(self):
        from datetime import date

        from .periodos import periodo
        hoje = date(2026, 11, 3)  # uma terça-feira
        p = periodo('semana', hoje)
        self.assertEqual((p['inicio'], p['fim']), (date(2026, 11, 2), date(2026, 11, 8)))
        self.assertEqual((p['anterior_inicio'], p['anterior_fim']), (date(2026, 10, 26), date(2026, 11, 1)))
        p = periodo('semana_passada', hoje)
        self.assertEqual((p['inicio'], p['rotulo_anterior']), (date(2026, 10, 26), 'semana retrasada'))
        p = periodo('mes', hoje)
        self.assertEqual((p['inicio'], p['fim'], p['anterior_fim']),
                         (date(2026, 11, 1), date(2026, 11, 30), date(2026, 10, 31)))
        self.assertEqual((p['rotulo_atual'], p['rotulo_anterior']), ('novembro', 'outubro'))
        p = periodo('mes_passado', hoje)
        self.assertEqual((p['inicio'], p['fim'], p['anterior_inicio']),
                         (date(2026, 10, 1), date(2026, 10, 31), date(2026, 9, 1)))
        # virada de ano e opção inválida
        p = periodo('mes_passado', date(2027, 1, 15))
        self.assertEqual((p['inicio'], p['anterior_inicio']), (date(2026, 12, 1), date(2026, 11, 1)))
        self.assertEqual(periodo('qualquer', hoje)['chave'], 'semana')

    def test_grafico_do_mes(self):
        from datetime import date

        from .periodos import periodo
        from .views import grafico
        p = periodo('mes', date(2026, 10, 15))  # outubro (31 dias) × setembro (30)
        colunas, _ = grafico({date(2026, 10, 2): 50, date(2026, 9, 2): 20}, p, date(2026, 10, 15))
        self.assertEqual(len(colunas), 31)
        self.assertEqual((colunas[1]['atual'], colunas[1]['anterior']), (50, 20))
        self.assertIsNone(colunas[20]['atual'])       # dia 21 ainda não chegou
        self.assertIsNone(colunas[30]['anterior'])    # setembro não tem dia 31

    def test_constancia_do_periodo(self):
        from datetime import date

        from .periodos import periodo
        from .views import constancia
        hoje = date(2026, 10, 15)
        por_dia = {date(2026, 10, 1): 30, date(2026, 10, 2): 90, date(2026, 9, 30): 500}
        # outubro de 2026 começa numa quinta: 5 colunas (29/09 a 01/11)
        semanas, resumo = constancia(por_dia, periodo('mes', hoje), hoje)
        self.assertEqual([s['inicio'] for s in semanas][0], date(2026, 9, 28))
        self.assertEqual(len(semanas), 5)
        primeira = semanas[0]['dias']
        self.assertTrue(primeira[2]['fora'])            # 30/09 é de setembro: não conta
        self.assertFalse(primeira[3]['fora'])           # 01/10
        self.assertTrue(semanas[2]['dias'][4]['futuro'])  # 16/10 ainda não chegou
        self.assertEqual((resumo['dias_com_estudo'], resumo['dias_passados'], resumo['media']), (2, 15, 60))
        self.assertEqual(resumo['maior']['data'], date(2026, 10, 2))
        # semana: uma coluna só
        semanas, resumo = constancia(por_dia, periodo('semana', hoje), hoje)
        self.assertEqual((len(semanas), resumo['dias_passados'], resumo['maior']), (1, 4, None))

    def test_filtro_muda_disciplinas_e_fica_guardado(self):
        categoria = Categoria.objects.create(nome='CC')
        redes = Disciplina.objects.create(categoria=categoria, nome='Redes 2')
        hoje = timezone.localdate()
        dias_ate_mes_passado = (hoje - (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)).days
        criar_sessao(40, dias_atras=dias_ate_mes_passado, disciplina=redes)  # dia 1 do mês passado

        nomes = lambda r: [l['disciplina__nome'] for l in r.context['por_disciplina']]
        self.assertEqual(nomes(self.client.get(reverse('dashboard:index') + '?periodo=semana')), [])
        resposta = self.client.get(reverse('dashboard:index') + '?periodo=mes_passado')
        self.assertEqual(nomes(resposta), ['Redes 2'])
        # sem ?periodo, lembra a última escolha
        resposta = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resposta.context['periodo']['chave'], 'mes_passado')
        self.assertContains(resposta, 'class="ativo"')

    def test_resumo_dos_projetos(self):
        from projetos.models import EntradaDiario, Funcionalidade, Projeto
        studyhub = Projeto.objects.create(nome='Studyhub', status='ativo')
        Projeto.objects.create(nome='Projeto pausado', status='pausado')
        agora = timezone.now()
        Funcionalidade.objects.create(projeto=studyhub, titulo='Flashcards', status='feito', concluida_em=agora)
        Funcionalidade.objects.create(projeto=studyhub, titulo='Antiga', status='feito',
                                      concluida_em=agora - timedelta(days=60))
        Funcionalidade.objects.create(projeto=studyhub, titulo='Questionário', status='fazendo')
        Funcionalidade.objects.create(projeto=studyhub, titulo='Planejador', status='backlog')
        EntradaDiario.objects.create(projeto=studyhub, fiz='Fiz os flashcards')
        SessaoPomodoro.objects.create(duracao_minutos=50, projeto=studyhub)

        resposta = self.client.get(reverse('dashboard:index') + '?periodo=semana')
        resumo, = resposta.context['projetos']  # o pausado não aparece
        self.assertEqual((resumo['feitas_total'], resumo['total'], resumo['porcentagem']), (2, 4, 50))
        self.assertEqual([f.titulo for f in resumo['feitas']], ['Flashcards'])  # "Antiga" fica fora da semana
        self.assertEqual([f.titulo for f in resumo['fazendo']], ['Questionário'])
        self.assertEqual((resumo['minutos'], resumo['diario_dias']), (50, 0))
        self.assertContains(resposta, 'Fiz os flashcards')
        self.assertNotContains(resposta, 'Projeto pausado')

    def test_feitas_mostra_no_maximo_cinco(self):
        from projetos.models import Funcionalidade, Projeto
        projeto = Projeto.objects.create(nome='Studyhub', status='ativo')
        for i in range(7):
            Funcionalidade.objects.create(projeto=projeto, titulo=f'F{i}', status='feito', concluida_em=timezone.now())
        resposta = self.client.get(reverse('dashboard:index') + '?periodo=semana')
        resumo = resposta.context['projetos'][0]
        self.assertEqual((len(resumo['feitas']), resumo['feitas_quantidade'], resumo['feitas_resto']), (5, 7, 2))
        self.assertContains(resposta, '+ 2 outras')


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


class SincronizacaoTests(TestCase):
    """Simula dois computadores usando um repositório Git local (nada vai para o GitHub)."""

    def setUp(self):
        import subprocess
        import tempfile
        from pathlib import Path

        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.raiz = Path(self.temp.name)
        self.repo = self.raiz / 'remoto.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(self.repo)], check=True)
        categoria = Categoria.objects.create(nome='Ciência da Computação', tipo='graduacao')
        self.redes = Disciplina.objects.create(categoria=categoria, nome='Redes 2')
        SessaoPomodoro.objects.create(duracao_minutos=25, disciplina=self.redes)

    def tearDown(self):
        self.temp.cleanup()

    def computador(self, nome):
        from django.test import override_settings
        return override_settings(DADOS_REPO=str(self.repo), DADOS_DIR=self.raiz / nome)

    def test_enviar_e_receber_em_outro_computador(self):
        from .sincronizacao import enviar, receber
        with self.computador('notebook'):
            self.assertIn('Dados enviados', enviar())
            self.assertIn('Nada para enviar', enviar())
        # "outro computador": banco vazio, recebe tudo
        from .sincronizacao import apagar_dados
        apagar_dados()
        self.assertFalse(SessaoPomodoro.objects.exists())
        with self.computador('desktop'):
            self.assertIn('recebidos', receber())
        self.assertEqual(SessaoPomodoro.objects.get().disciplina.nome, 'Redes 2')

    def test_nao_envia_por_cima_de_dados_mais_novos(self):
        from .sincronizacao import ErroSincronizacao, enviar
        with self.computador('notebook'):
            enviar()
        with self.computador('desktop'):
            SessaoPomodoro.objects.create(duracao_minutos=50)
            enviar(forcar=True)  # o desktop envia algo novo
        with self.computador('notebook'):
            SessaoPomodoro.objects.create(duracao_minutos=10)
            with self.assertRaisesMessage(ErroSincronizacao, 'receber_dados'):
                enviar()

    def test_nao_recebe_por_cima_de_mudancas_nao_enviadas(self):
        from .sincronizacao import ErroSincronizacao, enviar, receber
        with self.computador('notebook'):
            enviar()
            SessaoPomodoro.objects.create(duracao_minutos=10)  # mudança local não enviada
            with self.assertRaisesMessage(ErroSincronizacao, 'enviar_dados'):
                receber()
            self.assertIn('recebidos', receber(forcar=True))  # descarta a mudança local
        self.assertEqual(SessaoPomodoro.objects.count(), 1)

    def test_computador_novo_com_dados_pede_confirmacao(self):
        from .sincronizacao import ErroSincronizacao, enviar, receber
        with self.computador('notebook'):
            enviar()
        with self.computador('desktop'):
            with self.assertRaisesMessage(ErroSincronizacao, '--forcar'):
                receber()

    def test_repositorio_vazio(self):
        from .sincronizacao import ErroSincronizacao, receber
        with self.computador('desktop'):
            with self.assertRaisesMessage(ErroSincronizacao, 'vazio'):
                receber()
