from django.test import TestCase
from django.urls import reverse

from .models import Categoria, Disciplina, Periodo, Topico


class EstudosTests(TestCase):
    def setUp(self):
        self.grad = Categoria.objects.create(nome='Ciência da Computação', divisao='semestre')
        self.livres = Categoria.objects.create(nome='Estudos livres')

    def test_pagina_lista_categorias(self):
        resposta = self.client.get(reverse('estudos:index'))
        self.assertContains(resposta, 'Ciência da Computação')
        self.assertContains(resposta, '+ semestre')

    def test_criar_categoria_com_divisao(self):
        self.client.post(reverse('estudos:criar_categoria'), {'nome': 'Cloud Computing', 'divisao': 'modulo'})
        self.assertEqual(Categoria.objects.get(nome='Cloud Computing').divisao, 'modulo')

    def test_periodo_sem_nome_ganha_nome_automatico(self):
        url = reverse('estudos:criar_periodo', args=[self.grad.id])
        self.client.post(url, {'nome': ''})
        self.client.post(url, {'nome': ''})
        self.assertEqual(list(self.grad.periodos.values_list('nome', flat=True)), ['1º semestre', '2º semestre'])

        cloud = Categoria.objects.create(nome='Cloud', divisao='modulo')
        self.client.post(reverse('estudos:criar_periodo', args=[cloud.id]), {'nome': ''})
        self.assertEqual(cloud.periodos.get().nome, 'Módulo 1')

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
                         {'nome': 'Graduação', 'divisao': 'semestre'})
        periodo = Periodo.objects.create(categoria=self.grad, nome='5º')
        self.client.post(reverse('estudos:editar_periodo', args=[periodo.id]), {'nome': '5º semestre'})
        self.grad.refresh_from_db()
        periodo.refresh_from_db()
        self.assertEqual((self.grad.nome, periodo.nome), ('Graduação', '5º semestre'))

    def test_nome_vazio_nao_altera_e_avisa(self):
        resposta = self.client.post(reverse('estudos:editar_categoria', args=[self.grad.id]),
                                    {'nome': '', 'divisao': 'semestre'}, follow=True)
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
