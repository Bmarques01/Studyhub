from django import forms

from estudos.models import Disciplina, Topico

from .importacao import MAX_ALTERNATIVAS
from .models import Questao

ARQUIVO_MAXIMO = 1_000_000  # ~1 MB de texto


def conferir_topico(dados):
    """O tópico (opcional) precisa ser da disciplina escolhida."""
    topico, disciplina = dados.get('topico'), dados.get('disciplina')
    if topico and disciplina and topico.disciplina_id != disciplina.id:
        raise forms.ValidationError('O tópico escolhido não é dessa disciplina.')


class QuestaoForm(forms.Form):
    """Escrever (ou editar) uma questão. As alternativas chegam como uma lista de campos
    "alternativa" (na ordem A, B, C...) e "correta" diz qual posição é a certa."""

    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all(),
                                        error_messages={'required': 'Escolha a disciplina.'})
    topico = forms.ModelChoiceField(queryset=Topico.objects.all(), required=False)
    tipo = forms.ChoiceField(choices=Questao.TIPOS)
    enunciado = forms.CharField(max_length=5000, error_messages={'required': 'Escreva o enunciado.'})
    explicacao = forms.CharField(max_length=5000, required=False)
    resposta_vf = forms.ChoiceField(choices=[('V', 'Verdadeiro'), ('F', 'Falso')], required=False)
    resposta_aberta = forms.CharField(max_length=5000, required=False)
    correta = forms.IntegerField(required=False)

    def clean(self):
        dados = super().clean()
        conferir_topico(dados)
        tipo = dados.get('tipo')
        dados['alternativas'] = []
        dados['resposta'] = ''
        if tipo == 'multipla':
            textos = [texto.strip() for texto in self.data.getlist('alternativa')][:MAX_ALTERNATIVAS]
            # alternativas em branco são ignoradas; "correta" aponta para a posição no formulário
            pares = [(texto, i == dados.get('correta')) for i, texto in enumerate(textos) if texto]
            if len(pares) < 2:
                raise forms.ValidationError('Escreva pelo menos 2 alternativas.')
            if sum(certa for _, certa in pares) != 1:
                raise forms.ValidationError('Marque qual alternativa é a certa.')
            dados['alternativas'] = pares
        elif tipo == 'vf':
            if not dados.get('resposta_vf'):
                raise forms.ValidationError('Marque se a afirmação é verdadeira ou falsa.')
            dados['resposta'] = dados['resposta_vf']
        elif tipo == 'aberta':
            if not dados.get('resposta_aberta', '').strip():
                raise forms.ValidationError('Escreva a resposta esperada.')
            dados['resposta'] = dados['resposta_aberta'].strip()
        return dados


class ImportarForm(forms.Form):
    """Colar (ou enviar num arquivo .txt) várias questões no formato de importacao.py."""

    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all(),
                                        error_messages={'required': 'Escolha a disciplina.'})
    topico = forms.ModelChoiceField(queryset=Topico.objects.all(), required=False)
    texto = forms.CharField(required=False, max_length=ARQUIVO_MAXIMO, strip=False)
    arquivo = forms.FileField(required=False)

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get('arquivo')
        if not arquivo:
            return ''
        if arquivo.size > ARQUIVO_MAXIMO:
            raise forms.ValidationError('Arquivo grande demais (máximo 1 MB).')
        bruto = arquivo.read()
        try:
            return bruto.decode('utf-8-sig')  # utf-8-sig: aceita o arquivo com ou sem BOM
        except UnicodeDecodeError:
            return bruto.decode('latin-1')

    def clean(self):
        dados = super().clean()
        conferir_topico(dados)
        # o arquivo, se veio, vale mais que o texto colado
        dados['texto'] = dados.get('arquivo') or dados.get('texto') or ''
        if not dados['texto'].strip() and not self.errors:
            raise forms.ValidationError('Cole as questões ou escolha um arquivo .txt.')
        return dados


class QuestionarioForm(forms.Form):
    """Começar um questionário: de uma disciplina inteira ou de um tópico."""

    QUANTIDADES = [(5, '5'), (10, '10'), (20, '20'), (0, 'todas')]

    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all())
    topico = forms.ModelChoiceField(queryset=Topico.objects.all(), required=False)
    quantidade = forms.TypedChoiceField(choices=QUANTIDADES, coerce=int, required=False, empty_value=10)

    def clean(self):
        dados = super().clean()
        conferir_topico(dados)
        return dados

