from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pomodoro.models import SessaoPomodoro

from .models import Categoria, Disciplina, Periodo, Topico, proximo_letivo, semestre_letivo


class EstudosTests(TestCase):
    def setUp(self):
        self.grad = Categoria.objects.create(nome='Ciência da Computação', tipo='graduacao')
        self.livres = Categoria.objects.create(nome='Estudos livres')

    def test_pagina_lista_categorias(self):
        resposta = self.client.get(reverse('estudos:index'))
        self.assertContains(resposta, 'Ciência da Computação')
        self.assertContains(resposta, '+ semestre')

    def test_criar_categoria_com_tipo(self):
        self.client.post(reverse('estudos:criar_categoria'), {'nome': 'Cloud Computing', 'tipo': 'pos'})
        cloud = Categoria.objects.get(nome='Cloud Computing')
        self.assertEqual((cloud.tipo, cloud.divisao), ('pos', 'modulo'))

    def test_periodo_sem_nome_ganha_nome_automatico(self):
        url = reverse('estudos:criar_periodo', args=[self.grad.id])
        self.client.post(url, {'nome': ''})
        self.client.post(url, {'nome': ''})
        atual = semestre_letivo(timezone.localdate())
        self.assertEqual(list(self.grad.periodos.values_list('nome', flat=True)), [atual, proximo_letivo(atual)])

        cloud = Categoria.objects.create(nome='Cloud', tipo='pos')
        self.client.post(reverse('estudos:criar_periodo', args=[cloud.id]), {'nome': ''})
        self.assertEqual(cloud.periodos.get().nome, 'Módulo 1')

    def test_projetos_e_outro_nao_tem_divisao(self):
        projetos = Categoria.objects.create(nome='Projetos', tipo='projetos')
        self.assertEqual(projetos.divisao, '')
        self.assertEqual(self.livres.divisao, '')  # tipo padrão = outro
        resposta = self.client.get(reverse('estudos:index'))
        self.assertContains(resposta, 'projetos</span>')

    def test_criar_disciplina_dentro_do_periodo(self):
        periodo = Periodo.objects.create(categoria=self.grad, nome='5º semestre')
        self.client.post(reverse('estudos:criar_disciplina'),
                         {'local': f'p:{periodo.id}', 'nome': 'Redes 2', 'cor': '#a77bf3'})
        d = Disciplina.objects.get()
        self.assertEqual((d.categoria, d.periodo, d.cor), (self.grad, periodo, '#a77bf3'))

    def test_criar_disciplina_sem_periodo(self):
        self.client.post(reverse('estudos:criar_disciplina'),
                         {'local': f'c:{self.livres.id}', 'nome': 'Django', 'cor': '#e0609a'})
        d = Disciplina.objects.get()
        self.assertEqual((d.categoria, d.periodo), (self.livres, None))

    def test_local_invalido_nao_cria(self):
        self.client.post(reverse('estudos:criar_disciplina'), {'local': 'x:1', 'nome': 'X', 'cor': '#e0609a'})
        self.assertFalse(Disciplina.objects.exists())

    def test_cor_invalida_nao_cria(self):
        self.client.post(reverse('estudos:criar_disciplina'),
                         {'local': f'c:{self.livres.id}', 'nome': 'X', 'cor': 'rosa'})
        self.assertFalse(Disciplina.objects.exists())

    def test_mover_disciplina_para_outra_categoria_e_periodo(self):
        d = Disciplina.objects.create(categoria=self.livres, nome='Redes')
        periodo = Periodo.objects.create(categoria=self.grad, nome='5º semestre')
        self.client.post(reverse('estudos:editar_disciplina', args=[d.id]),
                         {'local': f'p:{periodo.id}', 'nome': 'Redes 2', 'cor': '#123abc'})
        d.refresh_from_db()
        self.assertEqual((d.nome, d.cor, d.categoria, d.periodo), ('Redes 2', '#123abc', self.grad, periodo))

    def test_excluir_periodo_mantem_disciplinas(self):
        periodo = Periodo.objects.create(categoria=self.grad, nome='5º semestre')
        d = Disciplina.objects.create(categoria=self.grad, periodo=periodo, nome='Redes 2')
        self.client.post(reverse('estudos:excluir_periodo', args=[periodo.id]))
        d.refresh_from_db()
        self.assertIsNone(d.periodo)
        self.assertEqual(d.categoria, self.grad)

    def test_renomear_categoria_e_periodo(self):
        self.client.post(reverse('estudos:editar_categoria', args=[self.grad.id]),
                         {'nome': 'Graduação', 'tipo': 'graduacao'})
        periodo = Periodo.objects.create(categoria=self.grad, nome='5º')
        self.client.post(reverse('estudos:editar_periodo', args=[periodo.id]), {'nome': '5º semestre'})
        self.grad.refresh_from_db()
        periodo.refresh_from_db()
        self.assertEqual((self.grad.nome, periodo.nome), ('Graduação', '5º semestre'))

    def test_nome_vazio_nao_altera_e_avisa(self):
        resposta = self.client.post(reverse('estudos:editar_categoria', args=[self.grad.id]),
                                    {'nome': '', 'tipo': 'graduacao'}, follow=True)
        self.grad.refresh_from_db()
        self.assertEqual(self.grad.nome, 'Ciência da Computação')
        self.assertContains(resposta, 'mensagem error')

    def test_renomear_topico(self):
        d = Disciplina.objects.create(categoria=self.grad, nome='Redes')
        t = Topico.objects.create(disciplina=d, nome='TCP')
        self.client.post(reverse('estudos:editar_topico', args=[t.id]), {'nome': 'TCP/IP'})
        t.refresh_from_db()
        self.assertEqual(t.nome, 'TCP/IP')

    def test_arquivar_e_reativar(self):
        d = Disciplina.objects.create(categoria=self.grad, nome='Redes')
        self.client.post(reverse('estudos:arquivar_disciplina', args=[d.id]))
        d.refresh_from_db()
        self.assertTrue(d.arquivada)
        self.client.post(reverse('estudos:arquivar_disciplina', args=[d.id]))
        d.refresh_from_db()
        self.assertFalse(d.arquivada)

    def test_excluir_categoria_apaga_tudo_dentro(self):
        periodo = Periodo.objects.create(categoria=self.grad, nome='1º semestre')
        d = Disciplina.objects.create(categoria=self.grad, periodo=periodo, nome='Redes')
        Topico.objects.create(disciplina=d, nome='TCP')
        self.client.post(reverse('estudos:excluir_categoria', args=[self.grad.id]))
        self.assertFalse(Periodo.objects.exists())
        self.assertFalse(Disciplina.objects.exists())
        self.assertFalse(Topico.objects.exists())


class SemestreLetivoTests(TestCase):
    def test_semestre_letivo(self):
        from datetime import date
        self.assertEqual(semestre_letivo(date(2026, 3, 10)), '2026/1')
        self.assertEqual(semestre_letivo(date(2026, 8, 1)), '2026/2')
        self.assertEqual(proximo_letivo('2026/1'), '2026/2')
        self.assertEqual(proximo_letivo('2026/2'), '2027/1')


class NotasTests(TestCase):
    """Regra: Grau Final = GA × 0,33 + GB × 0,67, aprova com 6,0."""

    def disciplina(self, ga=None, gb=None):
        categoria = Categoria.objects.create(nome='CC', tipo='graduacao')
        return Disciplina(categoria=categoria, nome='Redes 2',
                          nota_ga=None if ga is None else Decimal(ga),
                          nota_gb=None if gb is None else Decimal(gb))

    def test_sem_notas(self):
        d = self.disciplina()
        self.assertEqual(d.situacao, 'sem_notas')
        self.assertIsNone(d.gb_necessario)

    def test_gb_necessario(self):
        d = self.disciplina(ga='5')
        # (6 - 5×0,33) / 0,67 = 6,4925... → arredonda para cima: 6,50
        self.assertEqual(d.gb_necessario, Decimal('6.50'))
        self.assertEqual(d.situacao, 'possivel')

    def test_ga_alto_ja_garante(self):
        self.assertEqual(self.disciplina(ga='10').gb_necessario, Decimal('4.03'))

    def test_ga_zero_ainda_da_para_passar(self):
        # Com esses pesos, o pior caso (GA = 0) pede 8,96 no GB: sempre é possível passar
        d = self.disciplina(ga='0')
        self.assertEqual(d.gb_necessario, Decimal('8.96'))
        self.assertEqual(d.situacao, 'possivel')

    def test_grau_final(self):
        aprovada = self.disciplina(ga='7', gb='6')
        self.assertEqual(aprovada.grau_final, Decimal('6.33'))  # 2,31 + 4,02
        self.assertEqual(aprovada.situacao, 'aprovada')
        reprovada = self.disciplina(ga='4', gb='5')
        self.assertEqual(reprovada.grau_final, Decimal('4.67'))  # 1,32 + 3,35
        self.assertEqual(reprovada.situacao, 'reprovada')


class PaginaDisciplinaTests(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nome='Ciência da Computação', tipo='graduacao')
        periodo = Periodo.objects.create(categoria=categoria, nome='5º semestre', ordem=1)
        self.redes = Disciplina.objects.create(categoria=categoria, periodo=periodo, nome='Redes 2')
        self.enlace = Topico.objects.create(disciplina=self.redes, nome='Serviços de Enlace')
        Topico.objects.create(disciplina=self.redes, nome='Roteamento')

    def test_pagina_abre_com_dados(self):
        SessaoPomodoro.objects.create(duracao_minutos=25, disciplina=self.redes, topico=self.enlace)
        SessaoPomodoro.objects.create(duracao_minutos=50, disciplina=self.redes)
        resposta = self.client.get(reverse('estudos:disciplina', args=[self.redes.id]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['minutos_total'], 75)
        self.assertEqual(resposta.context['sem_topico'], 50)
        self.assertEqual(resposta.context['semanas'][-1]['minutos'], 75)
        self.assertContains(resposta, 'nunca estudado')  # Roteamento
        self.assertContains(resposta, '5º semestre')

    def test_adicionar_topico_pela_pagina_da_disciplina(self):
        pagina = reverse('estudos:disciplina', args=[self.redes.id])
        resposta = self.client.post(reverse('estudos:criar_topico', args=[self.redes.id]),
                                    {'nome': 'IPv6', 'proximo': pagina})
        self.assertRedirects(resposta, pagina)
        self.assertTrue(self.redes.topicos.filter(nome='IPv6').exists())

    def test_salvar_notas(self):
        self.client.post(reverse('estudos:salvar_notas', args=[self.redes.id]), {'nota_ga': '5', 'nota_gb': ''})
        self.redes.refresh_from_db()
        self.assertEqual(self.redes.nota_ga, Decimal('5'))
        resposta = self.client.get(reverse('estudos:disciplina', args=[self.redes.id]))
        self.assertContains(resposta, '6,50')

    def test_nota_acima_de_10_e_recusada(self):
        self.client.post(reverse('estudos:salvar_notas', args=[self.redes.id]), {'nota_ga': '11', 'nota_gb': ''})
        self.redes.refresh_from_db()
        self.assertIsNone(self.redes.nota_ga)

    def test_cartao_na_pagina_estudos(self):
        resposta = self.client.get(reverse('estudos:index'))
        self.assertContains(resposta, reverse('estudos:disciplina', args=[self.redes.id]))
        self.assertContains(resposta, 'class="cartao-disciplina"')

    def test_estudar_agora_escolhe_disciplina_no_pomodoro(self):
        resposta = self.client.get(reverse('pomodoro:index') + f'?disciplina={self.redes.id}')
        self.assertContains(resposta, f'data-disciplina-inicial="{self.redes.id}"')
        resposta = self.client.get(reverse('pomodoro:index') + '?disciplina=999')
        self.assertContains(resposta, 'data-disciplina-inicial=""')

    def test_adicionar_prova_escolhe_disciplina_no_calendario(self):
        resposta = self.client.get(reverse('calendario:index') + f'?disciplina={self.redes.id}')
        self.assertContains(resposta, f'<option value="{self.redes.id}" selected>')
