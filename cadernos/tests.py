import json

from config.testes import TestCase
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
        self.assertContains(resposta, 'data-tela-cheia')
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

    def test_excluir_pela_lista_continua_na_pagina_aberta(self):
        caderno = Caderno.objects.create(nome='Redes')
        aberta = Pagina.objects.create(caderno=caderno, titulo='Aberta')
        outra = Pagina.objects.create(caderno=caderno, titulo='Rascunho')
        # a lista mostra uma lixeira para cada página
        resposta = self.client.get(reverse('cadernos:pagina', args=[aberta.id]))
        self.assertContains(resposta, 'class="excluir-na-lista"', count=2)
        resposta = self.client.post(reverse('cadernos:excluir_pagina', args=[outra.id]), {'voltar': aberta.id})
        self.assertRedirects(resposta, reverse('cadernos:pagina', args=[aberta.id]))
        self.assertFalse(Pagina.objects.filter(id=outra.id).exists())
        # "voltar" de outro caderno é ignorado
        alheia = Pagina.objects.create(caderno=Caderno.objects.create(nome='Outro'))
        resposta = self.client.post(reverse('cadernos:excluir_pagina', args=[aberta.id]), {'voltar': alheia.id})
        self.assertRedirects(resposta, reverse('cadernos:caderno', args=[caderno.id]), target_status_code=200)

    def test_estudar_isso_abre_pomodoro_no_topico(self):
        resposta = self.client.get(reverse('pomodoro:index') + f'?topico={self.bgp.id}')
        self.assertContains(resposta, f'data-disciplina-inicial="{self.redes.id}"')
        self.assertContains(resposta, f'data-segunda-inicial="{self.bgp.id}"')

    def test_disciplina_mostra_link_dos_cadernos(self):
        Caderno.objects.create(nome='Redes', disciplina=self.redes)
        resposta = self.client.get(reverse('estudos:disciplina', args=[self.redes.id]))
        self.assertContains(resposta, f'/cadernos/?disciplina={self.redes.id}')
        self.assertContains(resposta, '1 caderno')


GUIA = '<!DOCTYPE html><html><head><title>Caderno de Redes &amp; BGP</title></head><body><h1>BGP</h1><script>1</script></body></html>'


class MaterialTests(TestCase):
    def setUp(self):
        self.caderno = Caderno.objects.create(nome='Redes')
        self.url = reverse('cadernos:criar_material', args=[self.caderno.id])

    def test_colar_html_usa_o_titulo_do_material(self):
        resposta = self.client.post(self.url, {'titulo': '', 'html': GUIA})
        material = Pagina.objects.get()
        self.assertEqual((material.tipo, material.titulo, material.html), ('material', 'Caderno de Redes & BGP', GUIA))
        self.assertRedirects(resposta, reverse('cadernos:pagina', args=[material.id]))

    def test_enviar_arquivo_e_titulo_proprio(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        arquivo = SimpleUploadedFile('guia.html', ('﻿' + GUIA).encode('utf-8'), content_type='text/html')
        self.client.post(self.url, {'titulo': 'Meu guia', 'arquivo': arquivo})
        material = Pagina.objects.get()
        self.assertEqual((material.titulo, material.html), ('Meu guia', GUIA))  # sem o BOM

    def test_recusa_vazio_os_dois_ou_texto_sem_html(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.assertContains(self.client.post(self.url, {'html': '  '}, follow=True), 'Cole o HTML')
        self.assertContains(self.client.post(self.url, {'html': 'só texto'}, follow=True), 'não parece HTML')
        arquivo = SimpleUploadedFile('g.html', GUIA.encode(), content_type='text/html')
        self.assertContains(self.client.post(self.url, {'html': GUIA, 'arquivo': arquivo}, follow=True), 'não os dois')
        self.assertFalse(Pagina.objects.exists())

    def test_material_roda_isolado(self):
        material = Pagina.objects.create(caderno=self.caderno, tipo='material', html=GUIA, titulo='Guia')
        resposta = self.client.get(reverse('cadernos:material_html', args=[material.id]))
        html = resposta.content.decode()
        self.assertIn('<h1>BGP</h1><script>1</script>', html)  # o guia vai inteiro (com a ponte no <head>)
        # mesmo aberto direto, o guia fica numa origem isolada
        self.assertIn('sandbox allow-scripts', resposta['Content-Security-Policy'])
        self.assertNotIn('allow-same-origin', resposta['Content-Security-Policy'])
        self.assertEqual(resposta['X-Frame-Options'], 'SAMEORIGIN')
        # a página do caderno mostra o iframe isolado + o bloco de anotações; o HTML não vai direto na página
        pagina = self.client.get(reverse('cadernos:pagina', args=[material.id]))
        self.assertContains(pagina, 'sandbox="allow-scripts allow-popups allow-modals"')
        self.assertContains(pagina, 'suas anotações')
        self.assertNotContains(pagina, '<h1>BGP</h1>')
        # página escrita não tem HTML para servir
        escrita = Pagina.objects.create(caderno=self.caderno, titulo='Notas')
        self.assertEqual(self.client.get(reverse('cadernos:material_html', args=[escrita.id])).status_code, 404)

    def test_anotacoes_do_material_salvam_e_o_html_fica(self):
        material = Pagina.objects.create(caderno=self.caderno, tipo='material', html=GUIA, titulo='Guia')
        self.client.post(reverse('cadernos:salvar_pagina', args=[material.id]),
                         data=json.dumps({'conteudo': DELTA, 'texto': 'BGP usa AS'}), content_type='application/json')
        material.refresh_from_db()
        self.assertEqual((material.conteudo, material.html), (DELTA, GUIA))

    def test_ponte_de_armazenamento(self):
        material = Pagina.objects.create(caderno=self.caderno, tipo='material', html=GUIA, titulo='Guia')
        url_salvar = reverse('cadernos:salvar_pagina', args=[material.id])
        salvar = lambda dados: self.client.post(url_salvar, data=json.dumps(dados), content_type='application/json')
        # o guia marcou uma aula como estudada → fica no banco
        self.assertEqual(salvar({'armazenamento': {'progresso': '{"aula2":true}'}}).status_code, 200)
        material.refresh_from_db()
        self.assertEqual(material.armazenamento, {'progresso': '{"aula2":true}'})
        # inválidos: valor que não é texto, ou numa página escrita
        self.assertEqual(salvar({'armazenamento': {'x': 1}}).status_code, 400)
        escrita = Pagina.objects.create(caderno=self.caderno, titulo='Notas')
        self.assertEqual(self.client.post(reverse('cadernos:salvar_pagina', args=[escrita.id]),
                                          data=json.dumps({'armazenamento': {}}),
                                          content_type='application/json').status_code, 400)

        # ao abrir, a ponte entra logo depois do <head>, com o que foi salvo
        material.armazenamento = {'nota': '</script><script>alert(1)</script>'}
        material.save()
        html = self.client.get(reverse('cadernos:material_html', args=[material.id])).content.decode()
        self.assertTrue(html.startswith('<!DOCTYPE html><html><head><script>'))
        self.assertIn("Object.defineProperty(window, 'localStorage'", html)
        self.assertIn('\\u003c/script>\\u003cscript>alert(1)', html)  # o texto salvo não fecha o <script>
        self.assertEqual(html.count('<script>alert(1)'), 0)
        self.assertTrue(html.endswith('<title>Caderno de Redes &amp; BGP</title></head><body><h1>BGP</h1><script>1</script></body></html>'))
