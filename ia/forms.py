from django import forms

from estudos.models import Disciplina, Topico
from questoes.forms import conferir_topico

from .gerador import PDF_MAXIMO, TEXTO_MAXIMO, TIPOS, eh_pdf

MAX_QUESTOES = 30
MAX_FLASHCARDS = 50


class GerarForm(forms.Form):
    """O pedido: de qual material (PDF, .txt ou texto colado) e o que gerar."""

    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all(),
                                        error_messages={'required': 'Escolha a disciplina.'})
    topico = forms.ModelChoiceField(queryset=Topico.objects.all(), required=False)
    arquivo = forms.FileField(required=False)
    texto = forms.CharField(required=False, max_length=TEXTO_MAXIMO)

    gerar_questoes = forms.BooleanField(required=False)
    quantidade_questoes = forms.IntegerField(required=False, min_value=1, max_value=MAX_QUESTOES, initial=10)
    tipos = forms.MultipleChoiceField(choices=list(TIPOS.items()), required=False, initial=['multipla', 'vf'])
    gerar_flashcards = forms.BooleanField(required=False)
    quantidade_flashcards = forms.IntegerField(required=False, min_value=1, max_value=MAX_FLASHCARDS, initial=15)
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

    def clean(self):
        dados = super().clean()
        conferir_topico(dados)
        if self.errors:
            return dados

        # o arquivo, se veio, vale mais que o texto colado
        if dados.get('arquivo'):
            tipo, conteudo, nome = dados['arquivo']
            dados['pdf'] = conteudo if tipo == 'pdf' else None
            dados['material_texto'] = conteudo if tipo == 'texto' else ''
            dados['material_nome'] = nome[:200]
        elif (dados.get('texto') or '').strip():
            dados['pdf'], dados['material_texto'], dados['material_nome'] = None, dados['texto'], 'texto colado'
        else:
            raise forms.ValidationError('Envie os slides (PDF), um arquivo .txt ou cole o texto da aula.')

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
