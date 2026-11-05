from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from estudos.models import Categoria, Disciplina, Topico

from .importacao import ler_questoes
from .models import Alternativa, Questao, Questionario, Resposta

EXEMPLO = """Aqui estão as questões:

1. P: Qual protocolo de transporte o BGP usa?
A) UDP
B) TCP *
C) ICMP
E: O BGP usa TCP na porta 179.

---

P: [V/F] O BGP é um protocolo de roteamento interno (IGP).
R: F
E: O BGP é um EGP,
usado entre sistemas autônomos.

P: [aberta] Diferencie IGP de EGP.
R: IGP roteia dentro de um AS;
EGP, entre ASes.
"""


class ImportacaoTests(TestCase):
    def test_le_os_tres_tipos(self):
        questoes, problemas = ler_questoes(EXEMPLO)
        self.assertEqual(problemas, [])
        self.assertEqual([q['tipo'] for q in questoes], ['multipla', 'vf', 'aberta'])
        multipla, vf, aberta = questoes
        self.assertEqual(multipla['enunciado'], 'Qual protocolo de transporte o BGP usa?')
        self.assertEqual(multipla['alternativas'], [('UDP', False), ('TCP', True), ('ICMP', False)])
        self.assertEqual(multipla['explicacao'], 'O BGP usa TCP na porta 179.')  # o "---" é ignorado
        self.assertEqual((vf['enunciado'], vf['resposta']), ('O BGP é um protocolo de roteamento interno (IGP).', 'F'))
        self.assertEqual(vf['explicacao'], 'O BGP é um EGP,\nusado entre sistemas autônomos.')
        self.assertEqual(aberta['resposta'], 'IGP roteia dentro de um AS;\nEGP, entre ASes.')

    def test_resposta_por_letra_e_vf_sem_etiqueta(self):
        texto = 'P: Quanto é 2+2?\nA) 3\nB. 4\nR: b\n\nP: A Terra é redonda.\nR: Verdadeiro.'
        questoes, problemas = ler_questoes(texto)
        self.assertEqual(problemas, [])
        self.assertEqual(questoes[0]['alternativas'], [('3', False), ('4', True)])
        self.assertEqual((questoes[1]['tipo'], questoes[1]['resposta']), ('vf', 'V'))

    def test_problemas_sao_avisados(self):
        texto = ('P: Sem certa\nA) um\nB) dois\n\n'
                 'P: Duas certas\nA) um *\nB) dois *\n\n'
                 'P: Só uma alternativa\nA) um *\n\n'
                 'P: [V/F] Sem resposta\n\n'
                 'P: Aberta sem resposta\n\n'
                 'P: Esta está certa\nR: V')
        questoes, problemas = ler_questoes(texto)
        self.assertEqual(len(questoes), 1)
        motivos = [motivo for _, motivo in problemas]
        self.assertEqual(len(motivos), 5)
        self.assertIn('nenhuma alternativa certa (marque com * no fim)', motivos)
        self.assertIn('mais de uma alternativa marcada como certa', motivos)
        self.assertIn('precisa de pelo menos 2 alternativas', motivos)
        self.assertIn('V/F sem a resposta (R: V ou R: F)', motivos)
        self.assertIn('sem resposta (R:)', motivos)
        self.assertEqual(problemas[0][0], 'Sem certa')


class Base(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nome='Ciência da Computação')
        self.redes = Disciplina.objects.create(nome='Redes', categoria=categoria)
        self.calculo = Disciplina.objects.create(nome='Cálculo', categoria=categoria)
        self.bgp = Topico.objects.create(disciplina=self.redes, nome='BGP')
        self.derivada = Topico.objects.create(disciplina=self.calculo, nome='Derivada')

    def multipla(self, enunciado='Qual porta o BGP usa?', topico=None):
        questao = Questao.objects.create(disciplina=self.redes, topico=topico, tipo='multipla', enunciado=enunciado)
        for i, (texto, certa) in enumerate([('80', False), ('179', True), ('443', False)]):
            Alternativa.objects.create(questao=questao, texto=texto, correta=certa, ordem=i)
        return questao


class PaginasTests(Base):
    def test_index_e_disciplina(self):
        self.multipla()
        resposta = self.client.get(reverse('questoes:index'))
        self.assertContains(resposta, 'Redes')
        self.assertContains(resposta, '1</strong> questão')
        resposta = self.client.get(reverse('questoes:disciplina', args=[self.redes.id]))
        self.assertContains(resposta, 'Qual porta o BGP usa?')
        self.assertContains(resposta, 'nunca respondida')
        self.assertContains(resposta, 'fazer questionário')

    def test_menu_e_ferramenta_da_disciplina(self):
        self.assertContains(self.client.get(reverse('questoes:index')), 'Questões')
        resposta = self.client.get(reverse('estudos:disciplina', args=[self.redes.id]))
        self.assertContains(resposta, reverse('questoes:disciplina', args=[self.redes.id]))


class EscreverTests(Base):
    def test_escrever_multipla(self):
        resposta = self.client.post(reverse('questoes:nova'), {
            'disciplina': self.redes.id, 'topico': self.bgp.id, 'tipo': 'multipla',
            'enunciado': 'Qual porta?', 'alternativa': ['80', '', '179', ''], 'correta': '2',
            'explicacao': 'Porta 179.',
        })
        questao = Questao.objects.get()
        self.assertRedirects(resposta, reverse('questoes:disciplina', args=[self.redes.id]) + f'#questao-{questao.id}')
        self.assertEqual(questao.topico, self.bgp)
        # a alternativa em branco some e a certa continua a certa (vira a B)
        self.assertEqual([(a.letra, a.texto, a.correta) for a in questao.alternativas.all()],
                         [('A', '80', False), ('B', '179', True)])

    def test_escrever_vf_e_aberta_e_outra(self):
        resposta = self.client.post(reverse('questoes:nova'), {
            'disciplina': self.redes.id, 'tipo': 'vf', 'enunciado': 'BGP é IGP.', 'resposta_vf': 'F', 'outra': '1'})
        self.assertRedirects(resposta, reverse('questoes:nova') + f'?disciplina={self.redes.id}&tipo=vf')
        self.client.post(reverse('questoes:nova'), {
            'disciplina': self.redes.id, 'tipo': 'aberta', 'enunciado': 'O que é AS?', 'resposta_aberta': 'Sistema autônomo'})
        self.assertEqual(list(Questao.objects.values_list('tipo', 'resposta')),
                         [('vf', 'F'), ('aberta', 'Sistema autônomo')])

    def test_erros_voltam_sem_perder_o_texto(self):
        casos = [
            ({'tipo': 'multipla', 'alternativa': ['80', '179'], 'correta': ''}, 'Marque qual alternativa é a certa.'),
            ({'tipo': 'multipla', 'alternativa': ['80', ''], 'correta': '0'}, 'Escreva pelo menos 2 alternativas.'),
            ({'tipo': 'vf'}, 'Marque se a afirmação é verdadeira ou falsa.'),
            ({'tipo': 'aberta', 'resposta_aberta': '  '}, 'Escreva a resposta esperada.'),
            ({'tipo': 'vf', 'resposta_vf': 'V', 'topico': self.derivada.id}, 'O tópico escolhido não é dessa disciplina.'),
        ]
        for extra, erro in casos:
            resposta = self.client.post(reverse('questoes:nova'), {
                'disciplina': self.redes.id, 'enunciado': 'Meu enunciado', **extra})
            self.assertContains(resposta, erro)
            self.assertContains(resposta, 'Meu enunciado')
        self.assertFalse(Questao.objects.exists())

    def test_editar_e_excluir(self):
        questao = self.multipla()
        resposta = self.client.get(reverse('questoes:editar', args=[questao.id]))
        self.assertContains(resposta, 'value="179"')
        self.client.post(reverse('questoes:editar', args=[questao.id]), {
            'disciplina': self.redes.id, 'tipo': 'vf', 'enunciado': 'Agora é V/F', 'resposta_vf': 'V'})
        questao.refresh_from_db()
        self.assertEqual((questao.tipo, questao.resposta, questao.alternativas.count()), ('vf', 'V', 0))
        self.client.post(reverse('questoes:excluir', args=[questao.id]))
        self.assertFalse(Questao.objects.exists())


class ImportarTests(Base):
    def test_previa_depois_salvar(self):
        dados = {'disciplina': self.redes.id, 'topico': self.bgp.id, 'texto': EXEMPLO + '\nP: Sem certa\nA) a\nB) b'}
        resposta = self.client.post(reverse('questoes:importar'), {**dados, 'acao': 'previa'})
        self.assertContains(resposta, '3 questões encontradas')
        self.assertContains(resposta, 'nenhuma alternativa certa')
        self.assertContains(resposta, 'salvar 3 questões')
        self.assertFalse(Questao.objects.exists())  # a prévia não grava nada

        resposta = self.client.post(reverse('questoes:importar'), {**dados, 'acao': 'salvar'})
        self.assertRedirects(resposta, reverse('questoes:disciplina', args=[self.redes.id]))
        self.assertEqual(Questao.objects.filter(disciplina=self.redes, topico=self.bgp).count(), 3)
        self.assertEqual(Alternativa.objects.filter(correta=True).get().texto, 'TCP')

    def test_arquivo_com_bom(self):
        arquivo = SimpleUploadedFile('questoes.txt', EXEMPLO.encode('utf-8-sig'), content_type='text/plain')
        resposta = self.client.post(reverse('questoes:importar'), {
            'disciplina': self.redes.id, 'arquivo': arquivo, 'acao': 'previa'})
        self.assertContains(resposta, '3 questões encontradas')
        self.assertContains(resposta, 'Qual protocolo de transporte o BGP usa?')  # o texto vai para a caixa

    def test_sem_nada_e_topico_de_outra_disciplina(self):
        resposta = self.client.post(reverse('questoes:importar'), {'disciplina': self.redes.id, 'acao': 'previa'})
        self.assertContains(resposta, 'Cole as questões ou escolha um arquivo .txt.')
        resposta = self.client.post(reverse('questoes:importar'), {
            'disciplina': self.redes.id, 'topico': self.derivada.id, 'texto': EXEMPLO, 'acao': 'salvar'})
        self.assertContains(resposta, 'O tópico escolhido não é dessa disciplina.')
        self.assertFalse(Questao.objects.exists())


class QuestionarioTests(Base):
    def setUp(self):
        super().setUp()
        self.q_multipla = self.multipla(topico=self.bgp)
        self.q_vf = Questao.objects.create(disciplina=self.redes, tipo='vf', enunciado='BGP é IGP.', resposta='F',
                                           explicacao='É EGP.')
        self.q_aberta = Questao.objects.create(disciplina=self.redes, tipo='aberta', enunciado='O que é AS?',
                                               resposta='Sistema autônomo')

    def comecar(self, **extra):
        self.client.post(reverse('questoes:criar_questionario'), {'disciplina': self.redes.id, 'quantidade': 0, **extra})
        item = Questionario.objects.first()
        item.questoes = [self.q_multipla.id, self.q_vf.id, self.q_aberta.id]  # ordem fixa para o teste
        item.save()
        return item

    def test_rodada_completa(self):
        item = self.comecar()
        url = reverse('questoes:questionario', args=[item.id])
        responder = reverse('questoes:responder', args=[item.id])

        # 1) múltipla escolha: a página não entrega qual é a certa
        resposta = self.client.get(url)
        self.assertContains(resposta, 'Qual porta o BGP usa?')
        self.assertNotContains(resposta, '✓ certa')
        errada = self.q_multipla.alternativas.get(texto='80')
        resposta = self.client.post(responder, {'questao': self.q_multipla.id, 'alternativa': errada.id})
        primeira = Resposta.objects.get()
        self.assertRedirects(resposta, url + f'?ver={primeira.id}')
        self.assertEqual((primeira.resposta_dada, primeira.acertou), ('A', False))
        resposta = self.client.get(url + f'?ver={primeira.id}')
        self.assertContains(resposta, '✗ Errou')
        self.assertContains(resposta, '✗ sua resposta')
        self.assertContains(resposta, '✓ certa')

        # responder de novo a mesma questão (botão "voltar" do navegador) não conta
        self.client.post(responder, {'questao': self.q_multipla.id, 'alternativa': errada.id})
        self.assertEqual(Resposta.objects.count(), 1)

        # 2) V/F
        self.assertContains(self.client.get(url), 'BGP é IGP.')
        self.client.post(responder, {'questao': self.q_vf.id, 'vf': 'F'})
        self.assertTrue(Resposta.objects.last().acertou)

        # 3) aberta: primeiro mostra a esperada (sem gravar), depois você diz se acertou
        resposta = self.client.post(responder, {'questao': self.q_aberta.id, 'texto': 'Um conjunto de redes'})
        self.assertContains(resposta, 'Sistema autônomo')
        self.assertContains(resposta, 'Um conjunto de redes')
        self.assertEqual(Resposta.objects.count(), 2)
        self.client.post(responder, {'questao': self.q_aberta.id, 'texto': 'Um conjunto de redes', 'acertou': 'sim'})
        self.assertEqual(Resposta.objects.last().resposta_dada, 'Um conjunto de redes')

        # resultado
        resposta = self.client.get(url)
        self.assertContains(resposta, '<strong>2</strong> de 3', html=False)
        self.assertContains(resposta, '67% de acerto')
        self.assertContains(resposta, 'refazer a errada')

        # refazer só as erradas
        resposta = self.client.post(reverse('questoes:refazer_erradas', args=[item.id]))
        novo = Questionario.objects.first()
        self.assertNotEqual(novo.id, item.id)
        self.assertEqual(novo.questoes, [self.q_multipla.id])

        # os acertos aparecem na página da disciplina
        resposta = self.client.get(reverse('questoes:disciplina', args=[self.redes.id]))
        self.assertContains(resposta, '0/1 acertos')
        self.assertContains(resposta, '1/1 acertos')

    def test_quantidade_e_topico(self):
        self.client.post(reverse('questoes:criar_questionario'), {'disciplina': self.redes.id, 'quantidade': 5})
        self.assertEqual(len(Questionario.objects.first().questoes), 3)
        self.client.post(reverse('questoes:criar_questionario'),
                         {'disciplina': self.redes.id, 'topicos': [self.bgp.id], 'quantidade': 0})
        item = Questionario.objects.first()
        self.assertEqual(item.questoes, [self.q_multipla.id])
        self.assertEqual(item.nome_dos_topicos(), 'BGP')
        self.assertContains(self.client.get(reverse('questoes:questionario', args=[item.id])), 'Questionário · BGP')

    def test_varios_topicos_e_sem_topico(self):
        ospf = Topico.objects.create(disciplina=self.redes, nome='OSPF')
        q_ospf = self.multipla('Qual métrica o OSPF usa?', topico=ospf)
        Topico.objects.create(disciplina=self.redes, nome='RIP')  # sem questões: não aparece para marcar

        resposta = self.client.get(reverse('questoes:disciplina', args=[self.redes.id]))
        self.assertContains(resposta, 'type="checkbox" name="topicos"', count=2)  # BGP e OSPF
        self.assertContains(resposta, 'type="checkbox" name="sem_topico"')  # as 2 questões sem tópico

        # BGP + OSPF: só as questões dos dois tópicos
        self.client.post(reverse('questoes:criar_questionario'),
                         {'disciplina': self.redes.id, 'topicos': [self.bgp.id, ospf.id], 'quantidade': 0})
        item = Questionario.objects.first()
        self.assertEqual(sorted(item.questoes), sorted([self.q_multipla.id, q_ospf.id]))
        self.assertEqual(item.nome_dos_topicos(), 'BGP, OSPF')

        # OSPF + sem tópico
        self.client.post(reverse('questoes:criar_questionario'),
                         {'disciplina': self.redes.id, 'topicos': [ospf.id], 'sem_topico': '1', 'quantidade': 0})
        item = Questionario.objects.first()
        self.assertEqual(sorted(item.questoes), sorted([q_ospf.id, self.q_vf.id, self.q_aberta.id]))
        self.assertEqual(item.nome_dos_topicos(), 'OSPF, sem tópico')

        # refazer as erradas mantém os mesmos tópicos
        Resposta.objects.create(questionario=item, questao=q_ospf, acertou=False)
        self.client.post(reverse('questoes:refazer_erradas', args=[item.id]))
        self.assertEqual(Questionario.objects.first().nome_dos_topicos(), 'OSPF, sem tópico')

    def test_topico_de_outra_disciplina_e_recusado(self):
        resposta = self.client.post(reverse('questoes:criar_questionario'),
                                    {'disciplina': self.redes.id, 'topicos': [self.derivada.id], 'quantidade': 0},
                                    follow=True)
        self.assertContains(resposta, 'O tópico escolhido não é dessa disciplina.')
        self.assertFalse(Questionario.objects.exists())

    def test_disciplina_sem_questoes(self):
        resposta = self.client.post(reverse('questoes:criar_questionario'), {'disciplina': self.calculo.id, 'quantidade': 10})
        self.assertRedirects(resposta, reverse('questoes:disciplina', args=[self.calculo.id]))
        self.assertFalse(Questionario.objects.exists())

    def test_questao_excluida_no_meio_e_pulada(self):
        item = self.comecar()
        self.q_multipla.delete()
        self.assertContains(self.client.get(reverse('questoes:questionario', args=[item.id])), 'BGP é IGP.')

    def test_resposta_invalida_nao_grava(self):
        item = self.comecar()
        responder = reverse('questoes:responder', args=[item.id])
        outra = self.multipla('Outra')  # alternativa de outra questão
        self.client.post(responder, {'questao': self.q_multipla.id, 'alternativa': outra.alternativas.first().id})
        self.client.post(responder, {'questao': self.q_vf.id, 'vf': 'F'})  # não é a questão da vez
        self.assertFalse(Resposta.objects.exists())
