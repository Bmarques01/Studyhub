from django import forms

from cadernos.models import Pagina
from estudos.models import Disciplina, Topico
from questoes.forms import conferir_topico

from .gerador import PDF_MAXIMO, TEXTO_MAXIMO, TIPOS, eh_pdf, texto_da_pagina

MAX_QUESTOES = 30
MAX_FLASHCARDS = 50


class MaterialForm(forms.Form):
    """O material da aula: PDF, .txt/.md ou texto colado (o arquivo vale mais que o texto).
    Depois do clean: dados['pdf'] (bytes ou None), dados['material_texto'] e dados['material_nome']."""

    arquivo = forms.FileField(required=False)
    texto = forms.CharField(required=False, max_length=TEXTO_MAXIMO)
    pedido_extra = forms.CharField(required=False, max_length=500)

    def clean_arquivo(self):
        """Devolve None ou (tipo, conteúdo, nome): ('pdf', bytes, ...) ou ('texto', str, ...)."""
        arquivo = self.cleaned_data.get('arquivo')
        if not arquivo:
            return None
        nome = arquivo.name.lower()
        if nome.endswith('.pdf'):
            if arquivo.size > PDF_MAXIMO:
                raise forms.ValidationError('PDF grande demais (máximo 20 MB).')
            conteudo = arquivo.read()
            if not eh_pdf(conteudo):
                raise forms.ValidationError('Esse arquivo não parece ser um PDF.')
            return 'pdf', conteudo, arquivo.name
        if nome.endswith(('.txt', '.md')):
            bruto = arquivo.read(TEXTO_MAXIMO * 4 + 1)
            try:
                texto = bruto.decode('utf-8-sig')
            except UnicodeDecodeError:
                texto = bruto.decode('latin-1')
            if len(texto) > TEXTO_MAXIMO:
                raise forms.ValidationError('Texto grande demais. Divida o material em partes.')
            return 'texto', texto, arquivo.name
        raise forms.ValidationError('Envie um PDF ou um arquivo de texto (.txt ou .md).')

    def material_extra(self, dados):
        """Outra fonte de material quando não veio arquivo nem texto (ex.: uma página do caderno)."""
        return None

    def ler_material(self, dados):
        if dados.get('arquivo'):
            tipo, conteudo, nome = dados['arquivo']
            dados['pdf'] = conteudo if tipo == 'pdf' else None
            dados['material_texto'] = conteudo if tipo == 'texto' else ''
            dados['material_nome'] = nome[:200]
            return
        if (dados.get('texto') or '').strip():
            dados['pdf'], dados['material_texto'], dados['material_nome'] = None, dados['texto'], 'texto colado'
            return
        extra = self.material_extra(dados)
        if extra:
            dados['pdf'], (dados['material_texto'], dados['material_nome']) = None, extra
            return
        raise forms.ValidationError('Envie os slides (PDF), um arquivo .txt ou cole o texto da aula.')


class GerarForm(MaterialForm):
    """Questões e flashcards: de qual material e o que gerar."""

    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all(),
                                        error_messages={'required': 'Escolha a disciplina.'})
    topico = forms.ModelChoiceField(queryset=Topico.objects.all(), required=False)
    # Vindo do botão de uma página do caderno: o texto dela é o material
    pagina = forms.ModelChoiceField(queryset=Pagina.objects.all(), required=False)

    gerar_questoes = forms.BooleanField(required=False)
    quantidade_questoes = forms.IntegerField(required=False, min_value=1, max_value=MAX_QUESTOES, initial=10)
    tipos = forms.MultipleChoiceField(choices=list(TIPOS.items()), required=False, initial=['multipla', 'vf'])
    gerar_flashcards = forms.BooleanField(required=False)
    quantidade_flashcards = forms.IntegerField(required=False, min_value=1, max_value=MAX_FLASHCARDS, initial=15)

    def material_extra(self, dados):
        pagina = dados.get('pagina')
        if not pagina:
            return None
        texto = texto_da_pagina(pagina)
        if not texto.strip():
            raise forms.ValidationError('Essa página do caderno está vazia. Escreva algo nela ou envie um material.')
        return texto, f'página "{pagina.titulo}"'[:200]

    def clean(self):
        dados = super().clean()
        conferir_topico(dados)
        if self.errors:
            return dados
        self.ler_material(dados)

        if not dados.get('gerar_questoes') and not dados.get('gerar_flashcards'):
            raise forms.ValidationError('Marque o que gerar: questões, flashcards ou os dois.')
        if dados.get('gerar_questoes'):
            if not dados.get('quantidade_questoes'):
                raise forms.ValidationError(f'Diga quantas questões (de 1 a {MAX_QUESTOES}).')
            if not dados.get('tipos'):
                raise forms.ValidationError('Marque pelo menos um tipo de questão.')
        if dados.get('gerar_flashcards') and not dados.get('quantidade_flashcards'):
            raise forms.ValidationError(f'Diga quantos flashcards (de 1 a {MAX_FLASHCARDS}).')
        return dados


class ResumoForm(MaterialForm):
    """Resumo no caderno: o material vira um guia (página de material)."""

    DETALHES = [('curto', 'resumo curto'), ('completo', 'completo, com exemplos')]

    detalhe = forms.ChoiceField(choices=DETALHES, initial='completo')
    topico = forms.ModelChoiceField(queryset=Topico.objects.all(), required=False)

    def __init__(self, *args, caderno, **kwargs):
        super().__init__(*args, **kwargs)
        self.caderno = caderno

    def clean(self):
        dados = super().clean()
        topico = dados.get('topico')
        if topico and topico.disciplina_id != self.caderno.disciplina_id:
            raise forms.ValidationError('O tópico escolhido não é da disciplina deste caderno.')
        if self.errors:
            return dados
        self.ler_material(dados)
        return dados
