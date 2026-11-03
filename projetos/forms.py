from django import forms

from .models import EntradaDiario, Funcionalidade, Projeto, Tarefa


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = ['nome', 'descricao', 'status', 'tipo', 'data_inicio', 'data_fim', 'cor', 'tecnologias',
                  'link_repositorio', 'link_deploy']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].required = False  # sem escolha = pessoal

    def clean_tipo(self):
        return self.cleaned_data.get('tipo') or 'pessoal'

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get('data_inicio'), dados.get('data_fim')
        if inicio and fim and fim < inicio:
            raise forms.ValidationError('A data de fim não pode ser antes da data de início.')
        return dados


class NovaFuncionalidadeForm(forms.ModelForm):
    class Meta:
        model = Funcionalidade
        fields = ['titulo', 'tipo', 'prioridade', 'status']


class FuncionalidadeForm(forms.ModelForm):
    class Meta:
        model = Funcionalidade
        fields = ['titulo', 'descricao', 'tipo', 'prioridade', 'status', 'estimativa_horas']


class TarefaForm(forms.ModelForm):
    class Meta:
        model = Tarefa
        fields = ['texto']


class EntradaDiarioForm(forms.ModelForm):
    class Meta:
        model = EntradaDiario
        fields = ['data', 'fiz', 'aprendi', 'travei']

    def clean(self):
        dados = super().clean()
        if not any(dados.get(campo, '').strip() for campo in ('fiz', 'aprendi', 'travei')):
            raise forms.ValidationError('Escreva pelo menos uma coisa no diário.')
        return dados
