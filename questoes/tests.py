from django.core.files.uploadedfile import SimpleUploadedFile
from config.testes import TestCase
from django.urls import reverse

from estudos.models import Categoria, Disciplina, Periodo, Topico

from .importacao import ler_questoes
from .models import Alternativa, Erro, Questao, Questionario, Resposta, registrar_erro

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
        # as questões de cada tópico começam fechadas (abre clicando no nome do tópico)
        self.assertContains(resposta, 'aria-expanded="false"')
        self.assertContains(resposta, 'id="bloco-1" hidden')

    def test_nova_disciplina(self):
        # a janela oferece os períodos da graduação (e a categoria sem divisão, que vale ela mesma)
        graduacao = Categoria.objects.create(nome='Graduação', tipo='graduacao')
        semestre = Periodo.objects.create(categoria=graduacao, nome='2026/2')
        resposta = self.client.get(reverse('questoes:index'))
        self.assertContains(resposta, f'value="p:{semestre.id}"')
        self.assertContains(resposta, 'Graduação · 2026/2')

        resposta = self.client.post(reverse('questoes:nova_disciplina'),
                                    {'nome': 'Sistemas Operacionais', 'cor': '#5b4bd0', 'local': f'p:{semestre.id}'})
        nova = Disciplina.objects.get(nome='Sistemas Operacionais')
        self.assertRedirects(resposta, reverse('questoes:disciplina', args=[nova.id]))  # já abre a página dela
        self.assertEqual((nova.categoria, nova.periodo, nova.cor), (graduacao, semestre, '#5b4bd0'))

    def test_nova_disciplina_sem_nome_ou_sem_local(self):
        antes = Disciplina.objects.count()
        resposta = self.client.post(reverse('questoes:nova_disciplina'), {'nome': 'X', 'cor': '#e0609a', 'local': ''})
        self.assertRedirects(resposta, reverse('questoes:index'))
        self.client.post(reverse('questoes:nova_disciplina'), {'nome': '', 'cor': '#e0609a', 'local': 'c:1'})
        self.assertEqual(Disciplina.objects.count(), antes)

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

    def test_botao_de_arquivo(self):
        # o input de arquivo continua no form (escondido), com o botão e o nome do escolhido ao lado
        resposta = self.client.get(reverse('questoes:importar'))
        self.assertContains(resposta, 'type="file" name="arquivo"')
        self.assertContains(resposta, 'escolher .txt')
        self.assertContains(resposta, 'data-arquivo-nome')

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


class CadernoDeErrosTests(Base):
    def setUp(self):
        super().setUp()
        self.q = self.multipla(topico=self.bgp)
        self.q_vf = Questao.objects.create(disciplina=self.redes, tipo='vf', enunciado='BGP é IGP.', resposta='F')

    def responder_errado(self):
        """Um questionário de 1 questão (a múltipla), respondido com a alternativa errada."""
        item = Questionario.objects.create(disciplina=self.redes, questoes=[self.q.id])
        errada = self.q.alternativas.get(texto='80')
        self.client.post(reverse('questoes:responder', args=[item.id]), {'questao': self.q.id, 'alternativa': errada.id})
        return item, Resposta.objects.filter(questionario=item).get()

    def test_errar_no_questionario_entra_no_caderno(self):
        item, resposta = self.responder_errado()
        erro = Erro.objects.get()
        self.assertEqual((erro.questao, erro.resposta_dada, erro.vezes, erro.origem), (self.q, 'A', 1, ''))
        self.assertEqual(erro.texto_da_resposta_dada(), 'A) 80')
        # a correção pergunta "por que errou?"
        pagina = self.client.get(reverse('questoes:questionario', args=[item.id]) + f'?ver={resposta.id}')
        self.assertContains(pagina, 'Por que errou?')
        self.assertContains(pagina, 'falta de atenção')

        # errar de novo conta mais uma vez (não duplica)
        self.responder_errado()
        erro.refresh_from_db()
        self.assertEqual((Erro.objects.count(), erro.vezes), (1, 2))

    def test_acertar_nao_entra(self):
        item = Questionario.objects.create(disciplina=self.redes, questoes=[self.q_vf.id])
        self.client.post(reverse('questoes:responder', args=[item.id]), {'questao': self.q_vf.id, 'vf': 'F'})
        self.assertFalse(Erro.objects.exists())

    def test_motivo_e_anotacao(self):
        item, resposta = self.responder_errado()
        erro = Erro.objects.get()
        aqui = reverse('questoes:questionario', args=[item.id]) + f'?ver={resposta.id}'
        volta = self.client.post(reverse('questoes:salvar_erro', args=[erro.id]),
                                 {'motivo': 'confundi', 'anotacao': ' 179 é BGP ', 'proximo': aqui})
        self.assertRedirects(volta, aqui)  # volta para a correção
        erro.refresh_from_db()
        self.assertEqual((erro.motivo, erro.anotacao), ('confundi', '179 é BGP'))
        # só o motivo: a anotação fica como estava
        self.client.post(reverse('questoes:salvar_erro', args=[erro.id]), {'motivo': 'atencao'})
        erro.refresh_from_db()
        self.assertEqual((erro.motivo, erro.anotacao), ('atencao', '179 é BGP'))
        # link de fora do site não é seguido
        volta = self.client.post(reverse('questoes:salvar_erro', args=[erro.id]),
                                 {'motivo': 'atencao', 'proximo': 'https://exemplo.com/'})
        self.assertTrue(volta.url.startswith(reverse('questoes:erros')))

    def test_pagina_dominei_e_voltar(self):
        self.responder_errado()
        erro = Erro.objects.get()
        pagina = self.client.get(reverse('questoes:erros') + f'?disciplina={self.redes.id}')
        self.assertContains(pagina, 'Qual porta o BGP usa?')
        self.assertContains(pagina, 'tópicos que você mais erra')
        self.assertContains(pagina, '✗ sua resposta')

        self.client.post(reverse('questoes:erro_dominei', args=[erro.id]))
        erro.refresh_from_db()
        self.assertIsNotNone(erro.dominado_em)
        self.assertNotContains(self.client.get(reverse('questoes:erros')), 'Qual porta o BGP usa?')
        self.assertContains(self.client.get(reverse('questoes:erros') + '?dominados=1'), 'Qual porta o BGP usa?')

        # errar de novo uma dominada: ela volta para a lista
        registrar_erro(self.q, 'C')
        erro.refresh_from_db()
        self.assertIsNone(erro.dominado_em)
        # e o botão "voltar para os erros" também devolve
        self.client.post(reverse('questoes:erro_dominei', args=[erro.id]))
        self.client.post(reverse('questoes:erro_dominei', args=[erro.id]), {'acao': 'voltar'})
        erro.refresh_from_db()
        self.assertIsNone(erro.dominado_em)

    def test_acertar_uma_que_estava_nos_erros_oferece_dominei(self):
        registrar_erro(self.q_vf, 'V')
        item = Questionario.objects.create(disciplina=self.redes, questoes=[self.q_vf.id])
        self.client.post(reverse('questoes:responder', args=[item.id]), {'questao': self.q_vf.id, 'vf': 'F'})
        resposta = Resposta.objects.get()
        pagina = self.client.get(reverse('questoes:questionario', args=[item.id]) + f'?ver={resposta.id}')
        self.assertContains(pagina, 'Já domina?')

    def test_revisar_so_os_erros(self):
        registrar_erro(self.q, 'A')
        registrar_erro(self.q_vf, 'V')
        Erro.objects.filter(questao=self.q_vf).update(dominado_em=self.q_vf.criada_em)  # dominada: não entra
        resposta = self.client.post(reverse('questoes:revisar_erros'), {'disciplina': self.redes.id})
        item = Questionario.objects.get()
        self.assertRedirects(resposta, reverse('questoes:questionario', args=[item.id]))
        self.assertEqual((item.questoes, item.de_erros), ([self.q.id], True))
        self.assertContains(self.client.get(reverse('questoes:questionario', args=[item.id])), 'Revisão dos erros')

        # por tópico: "sem" = as questões sem tópico (nenhum erro pendente aqui)
        resposta = self.client.post(reverse('questoes:revisar_erros'), {'disciplina': self.redes.id, 'topico': 'sem'})
        self.assertRedirects(resposta, reverse('questoes:erros') + f'?disciplina={self.redes.id}')
        self.assertEqual(Questionario.objects.count(), 1)

    def test_erro_de_fora(self):
        dados = {'disciplina': self.redes.id, 'topico': self.bgp.id, 'origem': 'Prova GA',
                 'enunciado': 'Qual a porta do BGP?', 'resposta_dada': '80', 'resposta_certa': '179',
                 'motivo': 'nao_sabia', 'anotacao': 'decorar'}
        resposta = self.client.post(reverse('questoes:novo_erro'), dados)
        erro = Erro.objects.get()
        self.assertRedirects(resposta, reverse('questoes:erros') + f'?disciplina={self.redes.id}#erro-{erro.id}',
                             fetch_redirect_response=False)
        self.assertEqual((erro.origem, erro.motivo, erro.resposta_dada, erro.anotacao),
                         ('Prova GA', 'nao_sabia', '80', 'decorar'))
        self.assertEqual((erro.questao.tipo, erro.questao.resposta, erro.questao.topico), ('aberta', '179', self.bgp))

        # "salvar e anotar outro": volta com a mesma disciplina, tópico e prova
        resposta = self.client.post(reverse('questoes:novo_erro'), {**dados, 'outro': '1'})
        self.assertIn('origem=Prova+GA', resposta.url)
        self.assertContains(self.client.get(resposta.url), 'value="Prova GA"')

        # sem a resposta certa: não salva e mostra o erro
        resposta = self.client.post(reverse('questoes:novo_erro'), {**dados, 'resposta_certa': ''})
        self.assertContains(resposta, 'Escreva a resposta certa.')
        self.assertEqual(Erro.objects.count(), 2)

    def test_atalhos(self):
        registrar_erro(self.q, 'A')
        self.assertContains(self.client.get(reverse('questoes:disciplina', args=[self.redes.id])), 'erros (1)')
        self.assertContains(self.client.get(reverse('estudos:disciplina', args=[self.redes.id])), '1 para revisar')
        # no caderno de erros, o menu marca só "Erros"
        menu = self.client.get(reverse('questoes:erros')).content.decode()
        self.assertEqual(menu.count('class="menu-item ativo"'), 1)
        self.assertIn(f'href="{reverse("questoes:erros")}" class="menu-item ativo"', menu)

    def test_erros_de_antes_entram_pela_migracao(self):
        # as respostas erradas de antes do caderno existir viram erros (contando as vezes)
        from importlib import import_module

        from django.apps import apps
        migracao = import_module('questoes.migrations.0003_caderno_de_erros')
        for dada, acertou in [('A', False), ('B', True), ('C', False)]:
            Resposta.objects.create(questao=self.q, resposta_dada=dada, acertou=acertou)
        migracao.trazer_erros_antigos(apps, None)
        erro = Erro.objects.get()
        self.assertEqual((erro.vezes, erro.resposta_dada), (2, 'C'))


class CliqueiErradoTests(Base):
    """O "cliquei errado" da correção: apaga a última resposta e desfaz o caderno de erros."""

    def setUp(self):
        super().setUp()
        self.q = self.multipla(topico=self.bgp)
        self.q2 = self.multipla(enunciado='Qual porta o OSPF usa?')
        self.item = Questionario.objects.create(disciplina=self.redes, questoes=[self.q.id, self.q2.id])

    def responder(self, questao, texto):
        alternativa = questao.alternativas.get(texto=texto)
        self.client.post(reverse('questoes:responder', args=[self.item.id]),
                         {'questao': questao.id, 'alternativa': alternativa.id})
        return Resposta.objects.filter(questionario=self.item, questao=questao).get()

    def desfazer(self, resposta):
        return self.client.post(reverse('questoes:desfazer', args=[self.item.id, resposta.id]))

    def test_desfazer_erro_novo(self):
        resposta = self.responder(self.q, '80')
        pagina = self.client.get(reverse('questoes:questionario', args=[self.item.id]) + f'?ver={resposta.id}')
        self.assertContains(pagina, 'cliquei errado')
        self.desfazer(resposta)
        # a resposta some, a questão sai do caderno e volta a ser a da vez
        self.assertFalse(Resposta.objects.exists())
        self.assertFalse(Erro.objects.exists())
        pagina = self.client.get(reverse('questoes:questionario', args=[self.item.id]))
        self.assertEqual(pagina.context['questao'], self.q)

    def test_erro_antigo_so_conta_uma_vez_a_menos(self):
        antes = registrar_erro(self.q, 'C')
        resposta = self.responder(self.q, '80')
        self.assertEqual(Erro.objects.get().vezes, 2)
        self.desfazer(resposta)
        erro = Erro.objects.get()
        self.assertEqual((erro.id, erro.vezes), (antes.id, 1))

    def test_so_a_ultima_resposta(self):
        primeira = self.responder(self.q, '179')
        segunda = self.responder(self.q2, '80')
        pagina = self.client.get(reverse('questoes:questionario', args=[self.item.id]) + f'?ver={primeira.id}')
        self.assertNotContains(pagina, 'cliquei errado')
        self.desfazer(primeira)  # não é a última: nada muda
        self.assertEqual(Resposta.objects.count(), 2)
        self.desfazer(segunda)
        self.assertEqual(list(Resposta.objects.values_list('id', flat=True)), [primeira.id])

    def test_so_aceita_post(self):
        resposta = self.responder(self.q, '80')
        self.client.get(reverse('questoes:desfazer', args=[self.item.id, resposta.id]))
        self.assertTrue(Resposta.objects.exists())
