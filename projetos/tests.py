import json

from config.testes import TestCase
from django.urls import reverse

from pomodoro.models import SessaoPomodoro

from .models import EntradaDiario, Funcionalidade, Projeto, Tarefa


class ProjetoTests(TestCase):
    def setUp(self):
        self.projeto = Projeto.objects.create(nome='Studyhub', tecnologias='Python, Django ,  JavaScript')

    def func(self, titulo, status='a_fazer', **extra):
        return Funcionalidade.objects.create(projeto=self.projeto, titulo=titulo, status=status, **extra)

    def test_coluna_feito_mais_novo_em_cima(self):
        from datetime import timedelta

        from django.utils import timezone
        agora = timezone.now()
        antiga = self.func('Antiga', 'feito', ordem=0, concluida_em=agora - timedelta(days=10))
        nova = self.func('Nova', 'feito', ordem=5, concluida_em=agora)
        meio = self.func('Meio', 'feito', ordem=1, concluida_em=agora - timedelta(days=2))
        Funcionalidade.objects.filter(id=antiga.id).update(concluida_em=None)  # dado antigo, sem data
        resposta = self.client.get(reverse('projetos:projeto', args=[self.projeto.id]))
        feito = next(c for c in resposta.context['colunas'] if c['status'] == 'feito')
        self.assertEqual([f.titulo for f in feito['cartoes']], ['Nova', 'Meio', 'Antiga'])
        # as outras colunas continuam na ordem manual
        self.func('B', ordem=1)
        self.func('A', ordem=0)
        resposta = self.client.get(reverse('projetos:projeto', args=[self.projeto.id]))
        a_fazer = next(c for c in resposta.context['colunas'] if c['status'] == 'a_fazer')
        self.assertEqual([f.titulo for f in a_fazer['cartoes']], ['A', 'B'])

    def test_tipo_e_datas(self):
        from datetime import date, timedelta

        from django.utils import timezone
        # criar sem escolher o tipo: pessoal
        self.client.post(reverse('projetos:criar_projeto'), {'nome': 'Novo', 'status': 'ativo', 'cor': '#a77bf3'})
        self.assertEqual(Projeto.objects.get(nome='Novo').tipo, 'pessoal')

        url = reverse('projetos:editar_projeto', args=[self.projeto.id])
        dados = {'nome': 'Time Tracking', 'status': 'ativo', 'cor': '#6250d6', 'tipo': 'trabalho',
                 'data_inicio': '2026-10-07', 'data_fim': ''}
        self.client.post(url, dados)
        self.projeto.refresh_from_db()
        self.assertEqual((self.projeto.tipo, self.projeto.data_inicio, self.projeto.data_fim),
                         ('trabalho', date(2026, 10, 7), None))
        hoje = timezone.localdate()
        self.assertEqual(self.projeto.dias, (hoje - date(2026, 10, 7)).days + 1)

        # fim antes do início: não salva
        resposta = self.client.post(url, {**dados, 'data_fim': '2026-10-01'}, follow=True)
        self.assertContains(resposta, 'não pode ser antes')
        self.projeto.refresh_from_db()
        self.assertIsNone(self.projeto.data_fim)

        # terminado: conta só até o fim
        self.client.post(url, {**dados, 'data_fim': '2026-10-16'})
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.dias, 10)

        resposta = self.client.get(reverse('projetos:index'))
        self.assertContains(resposta, 'trabalho')
        self.assertContains(resposta, '07/10/2026 →')
        resposta = self.client.get(reverse('projetos:projeto', args=[self.projeto.id]))
        self.assertContains(resposta, '16/10/2026')
        self.assertContains(resposta, '10 dias')

    def test_lista_de_tecnologias(self):
        self.assertEqual(self.projeto.lista_tecnologias, ['Python', 'Django', 'JavaScript'])

    def test_criar_projeto_abre_a_pagina_dele(self):
        resposta = self.client.post(reverse('projetos:criar_projeto'),
                                    {'nome': 'Time Tracking', 'status': 'ativo', 'cor': '#a77bf3'})
        novo = Projeto.objects.get(nome='Time Tracking')
        self.assertRedirects(resposta, reverse('projetos:projeto', args=[novo.id]))

    def test_lista_mostra_progresso(self):
        self.func('Pomodoro', 'feito')
        self.func('Flashcards')
        resposta = self.client.get(reverse('projetos:index'))
        self.assertContains(resposta, 'Studyhub')
        self.assertEqual(resposta.context['projetos'][0].progresso, 50)

    def test_kanban_separa_colunas(self):
        self.func('Pomodoro', 'feito')
        self.func('Projetos', 'fazendo')
        self.func('Flashcards', 'backlog')
        resposta = self.client.get(reverse('projetos:projeto', args=[self.projeto.id]))
        colunas = {c['status']: [f.titulo for f in c['cartoes']] for c in resposta.context['colunas']}
        self.assertEqual(colunas, {'backlog': ['Flashcards'], 'a_fazer': [], 'fazendo': ['Projetos'],
                                   'feito': ['Pomodoro']})

    def test_criar_funcionalidade_entra_no_fim_da_coluna(self):
        self.func('A', ordem=0)
        url = reverse('projetos:criar_funcionalidade', args=[self.projeto.id])
        self.client.post(url, {'titulo': 'B', 'tipo': 'bug', 'prioridade': 'alta', 'status': 'a_fazer'})
        b = Funcionalidade.objects.get(titulo='B')
        self.assertEqual((b.tipo, b.prioridade, b.ordem), ('bug', 'alta', 1))

    def test_arrastar_muda_coluna_e_ordem(self):
        a, b = self.func('A'), self.func('B', 'fazendo')
        resposta = self.client.post(reverse('projetos:mover', args=[a.id]),
                                    data=json.dumps({'status': 'fazendo', 'ordem': [a.id, b.id]}),
                                    content_type='application/json')
        self.assertEqual(resposta.status_code, 200)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((a.status, a.ordem, b.ordem), ('fazendo', 0, 1))

    def test_ordem_salva_aparece_na_pagina(self):
        c = self.func('C', 'fazendo', ordem=0)
        a = self.func('A', 'fazendo', ordem=1)
        Tarefa.objects.create(funcionalidade=a, texto='x')  # força a consulta com contagem
        resposta = self.client.get(reverse('projetos:projeto', args=[self.projeto.id]))
        fazendo = next(col for col in resposta.context['colunas'] if col['status'] == 'fazendo')
        self.assertEqual([f.titulo for f in fazendo['cartoes']], ['C', 'A'])

    def test_coluna_invalida_e_recusada(self):
        a = self.func('A')
        resposta = self.client.post(reverse('projetos:mover', args=[a.id]),
                                    data=json.dumps({'status': 'inventada'}), content_type='application/json')
        self.assertEqual(resposta.status_code, 400)

    def test_data_de_conclusao(self):
        a = self.func('A')
        self.assertIsNone(a.concluida_em)
        a.status = 'feito'
        a.save()
        self.assertIsNotNone(a.concluida_em)
        a.status = 'fazendo'
        a.save()
        self.assertIsNone(a.concluida_em)

    def test_checklist(self):
        a = self.func('A')
        self.client.post(reverse('projetos:criar_tarefa', args=[a.id]), {'texto': 'criar o model'})
        tarefa = Tarefa.objects.get()
        self.client.post(reverse('projetos:alternar_tarefa', args=[tarefa.id]))
        tarefa.refresh_from_db()
        self.assertTrue(tarefa.feita)
        resposta = self.client.get(reverse('projetos:projeto', args=[self.projeto.id]))
        self.assertContains(resposta, '☑ 1/1')

    def test_pagina_da_funcionalidade_mostra_tempo_e_estimativa(self):
        a = self.func('A', estimativa_horas=2)
        SessaoPomodoro.objects.create(duracao_minutos=90, projeto=self.projeto, funcionalidade=a)
        resposta = self.client.get(reverse('projetos:funcionalidade', args=[a.id]))
        self.assertEqual(resposta.context['minutos'], 90)
        self.assertEqual(resposta.context['pct_estimativa'], 75)

    def test_editar_funcionalidade(self):
        a = self.func('A')
        self.client.post(reverse('projetos:funcionalidade', args=[a.id]), {
            'titulo': 'Kanban', 'descricao': 'arrastar cartões', 'tipo': 'melhoria',
            'prioridade': 'baixa', 'status': 'fazendo', 'estimativa_horas': '3.5'})
        a.refresh_from_db()
        self.assertEqual((a.titulo, a.tipo, a.status, str(a.estimativa_horas)), ('Kanban', 'melhoria', 'fazendo', '3.5'))

    def test_diario(self):
        url = reverse('projetos:criar_entrada', args=[self.projeto.id])
        self.client.post(url, {'data': '2026-11-02', 'fiz': 'Kanban', 'aprendi': 'drag and drop', 'travei': ''})
        self.assertEqual(EntradaDiario.objects.get().aprendi, 'drag and drop')
        # entrada vazia não é salva
        self.client.post(url, {'data': '2026-11-02', 'fiz': '', 'aprendi': '', 'travei': ''})
        self.assertEqual(EntradaDiario.objects.count(), 1)


class PomodoroComProjetoTests(TestCase):
    def setUp(self):
        self.projeto = Projeto.objects.create(nome='Studyhub')
        self.kanban = Funcionalidade.objects.create(projeto=self.projeto, titulo='Kanban', status='fazendo')
        self.feita = Funcionalidade.objects.create(projeto=self.projeto, titulo='Pomodoro', status='feito')

    def test_projeto_aparece_no_pomodoro_com_funcionalidades_pendentes(self):
        resposta = self.client.get(reverse('pomodoro:index'))
        segunda = resposta.context['topicos_por_disciplina'][f'p:{self.projeto.id}']
        self.assertEqual([f['nome'] for f in segunda], ['Kanban'])  # a feita não aparece

    def test_trabalhar_nisso_escolhe_projeto_e_funcionalidade(self):
        resposta = self.client.get(reverse('pomodoro:index') + f'?funcionalidade={self.kanban.id}')
        self.assertContains(resposta, f'data-disciplina-inicial="p:{self.projeto.id}"')
        self.assertContains(resposta, f'data-segunda-inicial="{self.kanban.id}"')

    def test_registrar_sessao_no_projeto(self):
        resposta = self.client.post(reverse('pomodoro:registrar'), content_type='application/json',
                                    data=json.dumps({'duracao_minutos': 25, 'projeto_id': str(self.projeto.id),
                                                     'funcionalidade_id': str(self.kanban.id)}))
        self.assertEqual(resposta.json()['disciplina'], 'Studyhub')
        self.assertEqual(resposta.json()['topico'], 'Kanban')
        sessao = SessaoPomodoro.objects.get()
        self.assertEqual((sessao.projeto, sessao.funcionalidade), (self.projeto, self.kanban))

    def test_funcionalidade_de_outro_projeto_e_ignorada(self):
        outro = Projeto.objects.create(nome='Outro')
        self.client.post(reverse('pomodoro:registrar'), content_type='application/json',
                         data=json.dumps({'duracao_minutos': 25, 'projeto_id': outro.id,
                                          'funcionalidade_id': self.kanban.id}))
        self.assertIsNone(SessaoPomodoro.objects.get().funcionalidade)

    def test_dashboard_mostra_projeto(self):
        SessaoPomodoro.objects.create(duracao_minutos=50, projeto=self.projeto)
        resposta = self.client.get(reverse('dashboard:index'))
        self.assertContains(resposta, 'Studyhub')
