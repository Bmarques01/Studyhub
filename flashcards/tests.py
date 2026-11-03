import json
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Perfil
from dashboard.sincronizacao import APPS
from estudos.models import Categoria, Disciplina, Topico

from . import memoria
from .importacao import ler_cartoes
from .models import Flashcard, Revisao


class ImportacaoTests(TestCase):
    def test_le_varios_cartoes(self):
        texto = ('F: Qual porta o BGP usa?\nV: TCP, porta 179.\n\n'
                 'frente: O que é um AS?\nverso: Um conjunto de redes\nsob a mesma administração.\n')
        cartoes, problemas = ler_cartoes(texto)
        self.assertEqual(cartoes, [
            ('Qual porta o BGP usa?', 'TCP, porta 179.'),
            ('O que é um AS?', 'Um conjunto de redes\nsob a mesma administração.'),
        ])
        self.assertEqual(problemas, [])

    def test_minusculas_e_espacos(self):
        cartoes, _ = ler_cartoes('  f :  pergunta\n  v:resposta')
        self.assertEqual(cartoes, [('pergunta', 'resposta')])

    def test_blocos_incompletos_viram_problema(self):
        cartoes, problemas = ler_cartoes('V: sem pergunta\n\nF: sem resposta\n\nF: ok\nV: ok')
        self.assertEqual(cartoes, [('ok', 'ok')])
        self.assertEqual(problemas, ['sem pergunta', 'sem resposta'])

    def test_linha_em_branco_antes_do_verso(self):
        self.assertEqual(ler_cartoes('F: pergunta\n\nV: resposta')[0], [('pergunta', 'resposta')])

    def test_texto_sem_marcadores(self):
        self.assertEqual(ler_cartoes('só um texto qualquer'), ([], []))


class MemoriaTests(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nome='CC', tipo='graduacao')
        self.redes = Disciplina.objects.create(categoria=categoria, nome='Redes 2')
        self.so = Disciplina.objects.create(categoria=categoria, nome='Sistemas Operacionais')
        self.agora = timezone.now()

    def criar(self, disciplina=None, n=1):
        return [Flashcard.objects.create(disciplina=disciplina or self.redes, frente=f'p{i}', verso=f'r{i}')
                for i in range(n)]

    def test_texto_intervalo(self):
        textos = [memoria.texto_intervalo(timedelta(**t)) for t in (
            {'seconds': 30}, {'minutes': 10}, {'hours': 5}, {'days': 1}, {'days': 3},
            {'days': 60}, {'days': 548})]
        self.assertEqual(textos, ['<1 min', '10 min', '5 h', '1 dia', '3 dias', '2 meses', '1,5 ano'])

    def test_responder_cartao_novo(self):
        cartao, = self.criar()
        memoria.responder(cartao, 3, agora=self.agora, duracao_segundos=7)  # bom
        cartao.refresh_from_db()
        self.assertFalse(cartao.novo)
        self.assertEqual(cartao.estado, 1)  # ainda aprendendo: volta em minutos
        self.assertEqual(cartao.vencimento - self.agora, timedelta(minutes=10))
        revisao = Revisao.objects.get()
        self.assertEqual((revisao.nota, revisao.duracao_segundos), (3, 7))

    def test_facil_vai_para_dias(self):
        cartao, = self.criar()
        memoria.responder(cartao, 4, agora=self.agora)
        cartao.refresh_from_db()
        self.assertEqual(cartao.estado, 2)  # revisão
        self.assertGreaterEqual(cartao.vencimento - self.agora, timedelta(days=1))

    def test_intervalos_crescem_com_a_nota(self):
        cartao, = self.criar()
        textos = memoria.intervalos(cartao, self.agora)
        self.assertEqual(list(textos), [1, 2, 3, 4])
        vencimentos = [memoria.simular(cartao, n, self.agora).due for n in (1, 2, 3, 4)]
        self.assertEqual(vencimentos, sorted(vencimentos))

    def test_limite_de_novos_por_dia(self):
        perfil = Perfil.atual()
        perfil.flashcards_novos_por_dia = 2
        perfil.save()
        cartoes = self.criar(n=3)
        self.assertEqual(memoria.para_revisar(), 2)
        memoria.responder(cartoes[0], 4)  # um novo visto hoje (fácil: só volta em dias)
        self.assertEqual(memoria.vagas_de_novos(), 1)
        self.assertEqual(memoria.para_revisar(), 1)
        memoria.responder(cartoes[1], 4)
        self.assertEqual(memoria.para_revisar(), 0)
        self.assertIsNone(memoria.proximo_cartao())  # o 3º fica para amanhã

    def test_vencidos_vem_antes_dos_novos(self):
        antigo, novo = self.criar(n=2)
        memoria.responder(antigo, 3, agora=self.agora - timedelta(hours=1))  # venceu há 50 min
        self.assertEqual(memoria.proximo_cartao(agora=self.agora), antigo)

    def test_aprendendo_aparece_antes_da_hora_se_nao_houver_mais_nada(self):
        cartao, = self.criar()
        memoria.responder(cartao, 1, agora=self.agora)  # de novo: volta em 1 min
        self.assertEqual(memoria.proximo_cartao(agora=self.agora), cartao)
        self.assertEqual(memoria.para_revisar(agora=self.agora), 0)  # mas não conta como "vencido"

    def test_filtro_e_resumo_por_disciplina(self):
        self.criar(self.redes, n=2)
        self.criar(self.so, n=1)
        self.assertEqual(memoria.para_revisar(self.so), 1)
        resumo = memoria.resumo_por_disciplina()
        self.assertEqual(resumo[self.redes.id], {'total': 2, 'para_revisar': 2})
        self.assertEqual(resumo[self.so.id], {'total': 1, 'para_revisar': 1})


class PaginasTests(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nome='CC', tipo='graduacao')
        self.redes = Disciplina.objects.create(categoria=categoria, nome='Redes 2')
        self.so = Disciplina.objects.create(categoria=categoria, nome='Sistemas Operacionais')
        self.bgp = Topico.objects.create(disciplina=self.redes, nome='BGP')
        self.escalonamento = Topico.objects.create(disciplina=self.so, nome='Escalonamento')

    def test_pagina_vazia_e_com_filtro(self):
        self.assertContains(self.client.get(reverse('flashcards:index')), 'Nenhum cartão')
        Flashcard.objects.create(disciplina=self.redes, frente='Porta do BGP?', verso='179')
        Flashcard.objects.create(disciplina=self.so, frente='O que é um processo?', verso='programa rodando')
        resposta = self.client.get(reverse('flashcards:index') + f'?disciplina={self.redes.id}')
        self.assertContains(resposta, 'Porta do BGP?')
        self.assertNotContains(resposta, 'O que é um processo?')
        self.assertContains(resposta, 'Sistemas Operacionais')  # continua no filtro
        # filtro inválido = todas
        self.assertContains(self.client.get(reverse('flashcards:index') + '?disciplina=abc'), 'O que é um processo?')

    def test_criar_cartao(self):
        self.client.post(reverse('flashcards:criar'), {
            'disciplina': self.redes.id, 'topico': self.bgp.id, 'frente': 'Porta?', 'verso': '179'})
        cartao = Flashcard.objects.get()
        self.assertEqual((cartao.disciplina, cartao.topico, cartao.frente), (self.redes, self.bgp, 'Porta?'))
        self.assertTrue(cartao.novo)

    def test_topico_de_outra_disciplina_nao_entra(self):
        resposta = self.client.post(reverse('flashcards:criar'), {
            'disciplina': self.redes.id, 'topico': self.escalonamento.id, 'frente': 'x', 'verso': 'y'},
            follow=True)
        self.assertFalse(Flashcard.objects.exists())
        self.assertContains(resposta, 'não é dessa disciplina')

    def test_importar(self):
        resposta = self.client.post(reverse('flashcards:importar'), {
            'disciplina': self.redes.id, 'topico': self.bgp.id,
            'texto': 'F: a\nV: b\n\nF: c\nV: d\n\nF: sem verso'}, follow=True)
        self.assertEqual(Flashcard.objects.filter(disciplina=self.redes, topico=self.bgp).count(), 2)
        self.assertContains(resposta, '2 cartão(ões) criado(s)')
        self.assertContains(resposta, '1 bloco(s) ignorado(s)')

    def test_importar_sem_cartoes(self):
        resposta = self.client.post(reverse('flashcards:importar'),
                                    {'disciplina': self.redes.id, 'texto': 'nada aqui'}, follow=True)
        self.assertContains(resposta, 'Não encontrei nenhum cartão')

    def test_editar_mantem_memoria_e_excluir(self):
        cartao = Flashcard.objects.create(disciplina=self.redes, frente='a', verso='b')
        memoria.responder(cartao, 4)
        vencimento = Flashcard.objects.get().vencimento
        self.client.post(reverse('flashcards:editar', args=[cartao.id]),
                         {'frente': 'a corrigida', 'verso': 'b', 'topico': self.bgp.id})
        cartao.refresh_from_db()
        self.assertEqual((cartao.frente, cartao.topico, cartao.vencimento), ('a corrigida', self.bgp, vencimento))
        self.client.post(reverse('flashcards:excluir', args=[cartao.id]))
        self.assertFalse(Flashcard.objects.exists())

    def test_salvar_limite(self):
        self.client.post(reverse('flashcards:salvar_limite'), {'flashcards_novos_por_dia': '35'})
        self.assertEqual(Perfil.atual().flashcards_novos_por_dia, 35)
        self.client.post(reverse('flashcards:salvar_limite'), {'flashcards_novos_por_dia': '0'})
        self.assertEqual(Perfil.atual().flashcards_novos_por_dia, 35)

    def test_revisao_pelo_json(self):
        a = Flashcard.objects.create(disciplina=self.redes, frente='a', verso='b', topico=self.bgp)
        Flashcard.objects.create(disciplina=self.so, frente='c', verso='d')
        self.assertEqual(self.client.get(reverse('flashcards:revisar')).status_code, 200)

        dados = self.client.get(reverse('flashcards:proximo') + f'?disciplina={self.redes.id}').json()
        self.assertEqual(dados['cartao']['id'], a.id)
        self.assertEqual((dados['cartao']['topico'], dados['restantes']), ('BGP', 1))
        self.assertEqual(set(dados['cartao']['intervalos']), {'1', '2', '3', '4'})

        resposta = self.client.post(reverse('flashcards:responder', args=[a.id]),
                                    json.dumps({'nota': 4, 'duracao_segundos': 5, 'disciplina': self.redes.id}),
                                    content_type='application/json')
        dados = resposta.json()
        self.assertIsNone(dados['cartao'])  # Redes acabou (o cartão de SO não entra no filtro)
        self.assertEqual(dados['restantes'], 0)
        self.assertTrue(dados['proxima'])  # "o próximo volta em X dias"
        self.assertEqual(Revisao.objects.get().nota, 4)

    def test_responder_dados_invalidos(self):
        a = Flashcard.objects.create(disciplina=self.redes, frente='a', verso='b')
        url = reverse('flashcards:responder', args=[a.id])
        for corpo in ('{"nota": 9}', '{"nota": "x"}', 'não é json'):
            self.assertEqual(self.client.post(url, corpo, content_type='application/json').status_code, 400)
        self.assertFalse(Revisao.objects.exists())
        self.assertEqual(self.client.get(url).status_code, 405)  # só POST

    def test_aparece_no_dashboard_e_na_disciplina(self):
        self.assertNotContains(self.client.get(reverse('dashboard:index')), 'chip-flashcards')
        Flashcard.objects.create(disciplina=self.redes, frente='a', verso='b')
        self.assertContains(self.client.get(reverse('dashboard:index')), '1</strong> cartão para revisar')
        resposta = self.client.get(reverse('estudos:disciplina', args=[self.redes.id]))
        self.assertContains(resposta, '1 cartão · 1 hoje')

    def test_entra_na_sincronizacao(self):
        self.assertIn('flashcards', APPS)
