import json

from django.test import TestCase
from django.urls import reverse

from estudos.models import Categoria, Disciplina, Topico

from .models import Caderno, Pagina

DELTA = {'ops': [{'insert': 'BGP usa '}, {'insert': 'AS', 'attributes': {'bold': True}}, {'insert': '\n'}]}


class CadernoTests(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nome='Ciência da Computação', tipo='graduacao')
        self.redes = Disciplina.objects.create(categoria=categoria, nome='Redes 2')
        self.bgp = Topico.objects.create(disciplina=self.redes, nome='BGP')

    def salvar(self, pagina, **dados):
        return self.client.post(reverse('cadernos:salvar_pagina', args=[pagina.id]),
                                data=json.dumps(dados), content_type='application/json')

    def test_criar_caderno_livre_abre_a_primeira_pagina(self):
        resposta = self.client.post(reverse('cadernos:criar_caderno'), {'nome': 'Ideias', 'cor_capa': '#a77bf3'})
        caderno = Caderno.objects.get()
        pagina = caderno.paginas.get()
        self.assertIsNone(caderno.disciplina)
        self.assertRedirects(resposta, reverse('cadernos:pagina', args=[pagina.id]))

    def test_criar_caderno_da_disciplina(self):
        self.client.post(reverse('cadernos:criar_caderno'),
                         {'nome': 'Redes', 'disciplina': self.redes.id, 'cor_capa': '#e0609a'})
        self.assertEqual(Caderno.objects.get().disciplina, self.redes)

    def test_estante_filtra_por_disciplina(self):
        Caderno.objects.create(nome='Redes', disciplina=self.redes)
        Caderno.objects.create(nome='Ideias')
        resposta = self.client.get(reverse('cadernos:index') + f'?disciplina={self.redes.id}')
        self.assertEqual([c.nome for c in resposta.context['cadernos']], ['Redes'])

    def test_salvamento_automatico(self):
        pagina = Pagina.objects.create(caderno=Caderno.objects.create(nome='Redes', disciplina=self.redes))
        resposta = self.salvar(pagina, titulo='Aula 3 – BGP', conteudo=DELTA, texto='BGP usa AS\n',
                               topico_id=str(self.bgp.id))
        self.assertEqual(resposta.status_code, 200)
        pagina.refresh_from_db()
        self.assertEqual((pagina.titulo, pagina.conteudo, pagina.topico), ('Aula 3 – BGP', DELTA, self.bgp))
        self.assertIn('BGP usa AS', pagina.texto)

    def test_conteudo_invalido_e_recusado(self):
        pagina = Pagina.objects.create(caderno=Caderno.objects.create(nome='X'))
        self.assertEqual(self.salvar(pagina, conteudo='<script>alert(1)</script>').status_code, 400)
        self.assertEqual(self.salvar(pagina, conteudo={'ops': 'não é lista'}).status_code, 400)

    def test_topico_de_outra_disciplina_e_ignorado(self):
        outra = Disciplina.objects.create(categoria=self.redes.categoria, nome='BD')
        pagina = Pagina.objects.create(caderno=Caderno.objects.create(nome='BD', disciplina=outra))
        self.salvar(pagina, topico_id=str(self.bgp.id))
        pagina.refresh_from_db()
        self.assertIsNone(pagina.topico)

    def test_titulo_vazio_vira_sem_titulo(self):
        pagina = Pagina.objects.create(caderno=Caderno.objects.create(nome='X'))
        self.salvar(pagina, titulo='   ')
        pagina.refresh_from_db()
        self.assertEqual(pagina.titulo, 'Sem título')

    def test_pagina_mostra_editor_com_conteudo(self):
        caderno = Caderno.objects.create(nome='Redes', disciplina=self.redes, papel='quadriculado', fonte='manuscrita')
        pagina = Pagina.objects.create(caderno=caderno, titulo='BGP', conteudo=DELTA)
        resposta = self.client.get(reverse('cadernos:pagina', args=[pagina.id]))
        self.assertContains(resposta, 'id="editor"')
        self.assertContains(resposta, 'fonte-manuscrita papel-quadriculado')
        self.assertContains(resposta, 'id="conteudo-pagina"')
        self.assertContains(resposta, '▶ estudar isso')

    def test_abrir_caderno_vai_para_a_pagina_mais_recente(self):
        caderno = Caderno.objects.create(nome='Redes')
        Pagina.objects.create(caderno=caderno, titulo='Antiga')
        nova = Pagina.objects.create(caderno=caderno, titulo='Nova')
        self.salvar(nova, titulo='Nova editada')
        resposta = self.client.get(reverse('cadernos:caderno', args=[caderno.id]))
        self.assertRedirects(resposta, reverse('cadernos:pagina', args=[nova.id]))

    def test_aparencia(self):
        caderno = Caderno.objects.create(nome='Redes')
        self.client.post(reverse('cadernos:editar_caderno', args=[caderno.id]), {
            'nome': 'Redes 2', 'disciplina': self.redes.id, 'cor_capa': '#123456', 'papel': 'pontilhado',
            'fonte': 'livro', 'cor_destaque': '#fff3a3', 'cor_titulos': '#5b4bd0'})
        caderno.refresh_from_db()
        self.assertEqual((caderno.nome, caderno.papel, caderno.fonte, caderno.disciplina),
                         ('Redes 2', 'pontilhado', 'livro', self.redes))

    def test_excluir_pagina_e_caderno(self):
        caderno = Caderno.objects.create(nome='Redes')
        pagina = Pagina.objects.create(caderno=caderno)
        self.client.post(reverse('cadernos:excluir_pagina', args=[pagina.id]))
        self.assertFalse(Pagina.objects.exists())
        self.client.post(reverse('cadernos:excluir_caderno', args=[caderno.id]))
        self.assertFalse(Caderno.objects.exists())

    def test_estudar_isso_abre_pomodoro_no_topico(self):
        resposta = self.client.get(reverse('pomodoro:index') + f'?topico={self.bgp.id}')
        self.assertContains(resposta, f'data-disciplina-inicial="{self.redes.id}"')
        self.assertContains(resposta, f'data-segunda-inicial="{self.bgp.id}"')

    def test_disciplina_mostra_link_dos_cadernos(self):
        Caderno.objects.create(nome='Redes', disciplina=self.redes)
        resposta = self.client.get(reverse('estudos:disciplina', args=[self.redes.id]))
        self.assertContains(resposta, f'/cadernos/?disciplina={self.redes.id}')
        self.assertContains(resposta, '1 caderno')
