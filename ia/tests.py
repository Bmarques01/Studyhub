import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from config.testes import TestCase
from estudos.models import Categoria, Disciplina, Topico
from flashcards.importacao import ler_cartoes
from flashcards.models import Flashcard
from questoes.importacao import ler_questoes
from questoes.models import Questao

from . import gerador
from .models import Geracao, custo_do_mes

# O que a IA "devolveria" (no formato do esquema)
RESPOSTA = {
    'questoes': [
        {'tipo': 'multipla', 'enunciado': 'Qual protocolo de transporte o BGP usa?',
         'alternativas': [{'texto': 'UDP', 'correta': False}, {'texto': 'TCP', 'correta': True},
                          {'texto': 'ICMP', 'correta': False}, {'texto': 'nota 5*', 'correta': False}],
         'resposta': '', 'explicacao': 'Usa TCP na porta 179.'},
        {'tipo': 'vf', 'enunciado': 'O BGP é um IGP.', 'alternativas': [], 'resposta': 'F',
         'explicacao': 'É um EGP.'},
        {'tipo': 'aberta', 'enunciado': 'R: o que é um AS?\nExplique.', 'alternativas': [],
         'resposta': 'Um conjunto de redes sob a mesma administração.', 'explicacao': ''},
    ],
    'flashcards': [
        {'frente': 'Porta do BGP?', 'verso': 'TCP 179'},
        {'frente': 'O que é AS?', 'verso': 'V: um sistema autônomo'},
    ],
}


def mensagem_falsa(dados=RESPOSTA, stop_reason='end_turn', modelo='claude-opus-5-5'):
    """Imita o objeto que a biblioteca da Anthropic devolve (só o que o gerador usa)."""
    return SimpleNamespace(
        stop_reason=stop_reason, model=modelo,
        content=[SimpleNamespace(type='text', text=json.dumps(dados))],
        usage=SimpleNamespace(input_tokens=10_000, output_tokens=2_000),
    )


class GeradorTests(TestCase):
    def test_json_vira_texto_da_importacao(self):
        questoes, problemas = ler_questoes(gerador.questoes_em_texto(RESPOSTA['questoes']))
        self.assertEqual(problemas, [])
        self.assertEqual([q['tipo'] for q in questoes], ['multipla', 'vf', 'aberta'])
        # a certa continua sendo a B, mesmo com uma alternativa que terminava em "*"
        self.assertEqual([certa for _, certa in questoes[0]['alternativas']], [False, True, False, False])
        self.assertEqual(questoes[1]['resposta'], 'F')
        # um enunciado que começava com "R:" não vira resposta, e as quebras de linha somem
        self.assertEqual(questoes[2]['enunciado'], '· R: o que é um AS? Explique.')

        cartoes, problemas = ler_cartoes(gerador.flashcards_em_texto(RESPOSTA['flashcards']))
        self.assertEqual(problemas, [])
        self.assertEqual(cartoes[1], ('O que é AS?', '· V: um sistema autônomo'))

    def test_custo(self):
        # Opus 5.5: US$ 4 por milhão de entrada e US$ 20 por milhão de saída
        self.assertEqual(gerador.calcular_custo('claude-opus-5-5', 10_000, 2_000), Decimal('0.08'))
        self.assertEqual(gerador.calcular_custo('modelo-desconhecido', 1_000_000, 0), Decimal('4'))

    def test_pedido_e_material(self):
        pedido = gerador.montar_pedido('Redes', 'BGP', 5, ['multipla', 'vf'], 0, 'nível difícil')
        self.assertIn('Gere 5 questões', pedido)
        self.assertIn('Não gere flashcards', pedido)
        self.assertIn('nível difícil', pedido)
        pdf = gerador.conteudo_do_material(pdf=b'%PDF-1.4 teste')
        self.assertEqual(pdf['type'], 'document')
        self.assertEqual(pdf['source']['media_type'], 'application/pdf')
        self.assertEqual(gerador.conteudo_do_material(texto='aula')['type'], 'text')

    def test_resposta_cortada_ou_recusada(self):
        self.assertIsNotNone(gerador.ler_resposta(mensagem_falsa(stop_reason='max_tokens'))[1])
        self.assertIsNotNone(gerador.ler_resposta(mensagem_falsa(stop_reason='refusal'))[1])

    def test_sem_chave(self):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}):
            with self.assertRaisesMessage(gerador.ErroDaIA, 'Falta a chave'):
                gerador.pedir_ao_claude({}, 'pedido')


class TelasTests(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nome='Ciência da Computação')
        self.redes = Disciplina.objects.create(nome='Redes', categoria=categoria)
        self.bgp = Topico.objects.create(disciplina=self.redes, nome='BGP')
        self.url = reverse('ia:gerar')

    def pedir(self, **extra):
        dados = {'disciplina': self.redes.id, 'topico': self.bgp.id, 'texto': 'Aula sobre BGP...',
                 'gerar_questoes': 'on', 'quantidade_questoes': 3, 'tipos': ['multipla', 'vf', 'aberta'],
                 'gerar_flashcards': 'on', 'quantidade_flashcards': 2, 'pedido_extra': ''}
        dados.update(extra)
        return self.client.post(self.url, dados)

    def test_pagina_abre_com_a_disciplina(self):
        resposta = self.client.get(f'{self.url}?disciplina={self.redes.id}&topico={self.bgp.id}')
        self.assertContains(resposta, f'<option value="{self.redes.id}" selected>')
        self.assertContains(resposta, f'data-inicial="{self.bgp.id}"')
        # botões nas páginas das disciplinas
        self.assertContains(self.client.get(reverse('questoes:disciplina', args=[self.redes.id])), 'gerar com IA')
        self.assertContains(self.client.get(reverse('flashcards:disciplina', args=[self.redes.id])), 'gerar com IA')

    @patch('ia.gerador.pedir_ao_claude', return_value=mensagem_falsa())
    def test_gerar_revisar_e_salvar(self, falso):
        resposta = self.pedir()
        geracao = Geracao.objects.get()
        self.assertRedirects(resposta, reverse('ia:revisao', args=[geracao.id]))
        self.assertEqual(geracao.custo, Decimal('0.08'))
        self.assertEqual((geracao.pediu_questoes, geracao.pediu_flashcards), (3, 2))
        self.assertIn('Gere 3 questões', falso.call_args.args[1])
        self.assertEqual(Questao.objects.count(), 0)  # nada salvo antes da revisão

        revisao = self.client.get(reverse('ia:revisao', args=[geracao.id]))
        self.assertContains(revisao, 'salvar 3 questões')
        self.assertContains(revisao, 'salvar 2 flashcards')

        # edita o texto (tira uma questão) e atualiza a prévia: ainda não salva
        url_questoes = reverse('ia:salvar', args=[geracao.id, 'questoes'])
        so_duas = geracao.texto_questoes.rsplit('\n\nP:', 1)[0]
        self.client.post(url_questoes, {'texto': so_duas, 'acao': 'previa'})
        self.assertEqual(Questao.objects.count(), 0)
        self.assertContains(self.client.get(reverse('ia:revisao', args=[geracao.id])), 'salvar 2 questões')

        # salva as questões e os flashcards
        self.client.post(url_questoes, {'texto': so_duas, 'acao': 'salvar'})
        self.assertEqual(Questao.objects.filter(disciplina=self.redes, topico=self.bgp).count(), 2)
        self.client.post(reverse('ia:salvar', args=[geracao.id, 'flashcards']),
                         {'texto': geracao.texto_flashcards, 'acao': 'salvar'})
        self.assertEqual(Flashcard.objects.filter(disciplina=self.redes, topico=self.bgp).count(), 2)
        geracao.refresh_from_db()
        self.assertEqual((geracao.questoes_salvas, geracao.flashcards_salvos), (2, 2))

        # não salva duas vezes
        self.client.post(url_questoes, {'texto': so_duas, 'acao': 'salvar'})
        self.assertEqual(Questao.objects.count(), 2)
        self.assertContains(self.client.get(reverse('ia:revisao', args=[geracao.id])), '2 questões salvas')

    @patch('ia.gerador.pedir_ao_claude', return_value=mensagem_falsa())
    def test_pdf_vai_como_documento(self, falso):
        pdf = SimpleUploadedFile('aula.pdf', b'%PDF-1.4 slides', content_type='application/pdf')
        self.pedir(texto='', arquivo=pdf)
        material = falso.call_args.args[0]
        self.assertEqual(material['type'], 'document')
        self.assertEqual(Geracao.objects.get().material, 'aula.pdf')

    @patch('ia.gerador.pedir_ao_claude')
    def test_pedidos_invalidos_nao_chamam_a_ia(self, falso):
        self.assertContains(self.pedir(texto=''), 'Envie os slides', status_code=200)
        self.assertContains(self.pedir(gerar_questoes='', gerar_flashcards=''), 'Marque o que gerar')
        self.assertContains(self.pedir(tipos=[]), 'pelo menos um tipo')
        falso_pdf = SimpleUploadedFile('aula.pdf', b'nao sou pdf')
        self.assertContains(self.pedir(texto='', arquivo=falso_pdf), 'não parece ser um PDF')
        self.assertContains(self.pedir(texto='', arquivo=SimpleUploadedFile('a.docx', b'x')), 'Envie um PDF')
        falso.assert_not_called()
        self.assertEqual(Geracao.objects.count(), 0)

    @patch('ia.gerador.pedir_ao_claude', return_value=mensagem_falsa(stop_reason='max_tokens'))
    def test_resposta_cortada_fica_no_historico_com_custo(self, falso):
        resposta = self.pedir()
        self.assertContains(resposta, 'cortada')
        geracao = Geracao.objects.get()
        self.assertTrue(geracao.erro)
        self.assertEqual(custo_do_mes(), (Decimal('0.08'), 1))
        self.assertContains(self.client.get(self.url), 'não deu certo')

    @patch('ia.gerador.pedir_ao_claude', side_effect=gerador.ErroDaIA('Os créditos da API acabaram.'))
    def test_erro_da_api_aparece_e_nao_conta_custo(self, falso):
        self.assertContains(self.pedir(), 'Os créditos da API acabaram.')
        self.assertEqual(Geracao.objects.count(), 0)

    def test_tipo_invalido(self):
        geracao = Geracao.objects.create(disciplina=self.redes, material='x')
        self.assertEqual(self.client.post(reverse('ia:salvar', args=[geracao.id, 'outra'])).status_code, 404)
