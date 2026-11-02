from django import forms

from .models import EntradaDiario, Funcionalidade, Projeto, Tarefa


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = ['nome', 'descricao', 'status', 'cor', 'tecnologias', 'link_repositorio', 'link_deploy']


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
