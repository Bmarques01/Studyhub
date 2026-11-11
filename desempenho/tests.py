from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from config.testes import TestCase
from estudos.models import Categoria, Disciplina, Topico
from flashcards.models import Flashcard, Revisao
from questoes.models import Erro, Questao, Resposta

from . import calculo


class Base(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nome='Ciência da Computação')
        self.redes = Disciplina.objects.create(nome='Redes', categoria=categoria)
        self.calculo = Disciplina.objects.create(nome='Cálculo', categoria=categoria)
        self.bgp = Topico.objects.create(disciplina=self.redes, nome='BGP')
        self.icmp = Topico.objects.create(disciplina=self.redes, nome='ICMP')
        self.derivada = Topico.objects.create(disciplina=self.calculo, nome='Derivada')

    def responder(self, topico, resultados, dias_atras=0):
        """Uma resposta por item de resultados (True = acertou). A primeira é a mais recente."""
        questao = Questao.objects.create(disciplina=topico.disciplina, topico=topico, tipo='vf',
                                         enunciado='?', resposta='V')
        agora = timezone.now() - timedelta(days=dias_atras)
        for i, acertou in enumerate(resultados):
            Resposta.objects.create(questao=questao, acertou=acertou, respondida_em=agora - timedelta(minutes=i))
        return questao

    def revisar(self, topico, notas):
        cartao = Flashcard.objects.create(disciplina=topico.disciplina, topico=topico, frente='a', verso='b')
        agora = timezone.now()
        for i, nota in enumerate(notas):
            Revisao.objects.create(flashcard=cartao, nota=nota, revisada_em=agora - timedelta(minutes=i))
        return cartao


class CalculoTests(Base):
    def test_sem_dados_lista_vazia(self):
        self.assertEqual(calculo.pontos_fracos(), [])

    def test_porcentagens_e_ordem(self):
        self.responder(self.bgp, [True, False, False, False, True])        # 40%
        self.responder(self.icmp, [True] * 9 + [False])                    # 90%
        self.revisar(self.bgp, [1, 1, 3, 3, 3])                             # lembrou 60%
        self.responder(self.derivada, [True] * 7 + [False] * 3)            # 70%

        grupos = calculo.pontos_fracos()
        # Redes: questões (2+9)/15 = 73%, flashcards 60% → 67; Cálculo: 70 → Redes primeiro
        self.assertEqual([g['disciplina'] for g in grupos], [self.redes, self.calculo])
        redes = grupos[0]
        self.assertEqual(redes['questoes']['pct'], 73)
        self.assertEqual(redes['flashcards']['pct'], 60)
        self.assertEqual(redes['dominio'], 67)

        bgp, icmp = redes['topicos']
        self.assertEqual(bgp['topico'], self.bgp)
        self.assertEqual(bgp['questoes']['pct'], 40)
        self.assertEqual(bgp['flashcards']['pct'], 60)
        self.assertEqual(bgp['dominio'], 50)  # média das duas
        self.assertEqual(bgp['situacao']['chave'], 'fraco')
        self.assertEqual(icmp['dominio'], 90)
        self.assertEqual(icmp['situacao']['chave'], 'bem')
        self.assertIsNone(icmp['flashcards']['pct'])  # sem flashcards: vale só a parte das questões

    def test_poucos_dados_vao_para_o_fim(self):
        self.responder(self.bgp, [False, False])                 # só 2: não dá para dizer que é fraco
        self.responder(self.icmp, [True] * 5)
        bgp = next(t for t in calculo.pontos_fracos()[0]['topicos'] if t['topico'] == self.bgp)
        self.assertIsNone(bgp['dominio'])
        self.assertEqual(bgp['situacao']['chave'], 'poucos')
        self.assertEqual(bgp['questoes']['quantidade'], 2)
        self.assertEqual(calculo.pontos_fracos()[0]['topicos'][-1]['topico'], self.bgp)

    def test_so_as_respostas_recentes_contam(self):
        # 20 acertos recentes, 20 erros antigos: está bem agora e a setinha diz que subiu
        self.responder(self.bgp, [True] * 20 + [False] * 20)
        bgp = calculo.pontos_fracos()[0]['topicos'][0]
        self.assertEqual(bgp['questoes']['pct'], 100)
        self.assertEqual(bgp['questoes']['tendencia'], 'subiu')

    def test_tendencia_caiu(self):
        self.responder(self.bgp, [False] * 10 + [True] * 10 + [True] * 20)
        self.assertEqual(calculo.pontos_fracos()[0]['topicos'][0]['questoes']['tendencia'], 'caiu')

    def test_erros_no_caderno_e_botoes(self):
        questao = self.responder(self.bgp, [False] * 5)
        Erro.objects.create(questao=questao)
        Erro.objects.create(questao=self.responder(self.bgp, [False]), dominado_em=timezone.now())  # dominado: não conta
        bgp = calculo.pontos_fracos()[0]['topicos'][0]
        self.assertEqual(bgp['erros'], 1)
        self.assertTrue(bgp['tem_questoes'])
        self.assertFalse(bgp['tem_cartoes'])

    def test_mais_fracos_so_abaixo_de_bom(self):
        self.responder(self.bgp, [False] * 5)        # 0%
        self.responder(self.icmp, [True] * 5)        # 100%: indo bem, não entra
        self.responder(self.derivada, [True, True, True, False, False])  # 60%
        fracos = calculo.mais_fracos(calculo.pontos_fracos())
        self.assertEqual([t['topico'] for t in fracos], [self.bgp, self.derivada])
        self.assertEqual(fracos[0]['disciplina'], self.redes)


class PaginasTests(Base):
    def test_pagina_vazia(self):
        resposta = self.client.get(reverse('desempenho:index'))
        self.assertContains(resposta, 'Ainda não há resultados')

    def test_pagina_com_dados(self):
        self.responder(self.bgp, [False] * 5)
        self.revisar(self.icmp, [3] * 5)
        resposta = self.client.get(reverse('desempenho:index'))
        self.assertContains(resposta, 'BGP')
        self.assertContains(resposta, 'precisa de atenção')
        self.assertContains(resposta, 'praticar')  # BGP tem questões
        self.assertContains(resposta, f'{reverse("flashcards:revisar")}?disciplina={self.redes.id}&topico={self.icmp.id}')

    def test_praticar_cria_questionario_do_topico(self):
        self.responder(self.bgp, [False] * 5)
        resposta = self.client.post(reverse('questoes:criar_questionario'),
                                    {'disciplina': self.redes.id, 'topicos': self.bgp.id, 'quantidade': 10})
        self.assertEqual(resposta.status_code, 302)

    def test_bloco_no_dashboard(self):
        resposta = self.client.get(reverse('dashboard:index'))
        self.assertContains(resposta, 'onde melhorar')
        self.assertContains(resposta, 'os tópicos mais fracos aparecem aqui')
        self.responder(self.bgp, [False] * 5)
        resposta = self.client.get(reverse('dashboard:index'))
        self.assertContains(resposta, 'BGP')
        self.assertContains(resposta, '0%')

    def test_menu(self):
        resposta = self.client.get(reverse('desempenho:index'))
        self.assertContains(resposta, 'Onde melhorar')
