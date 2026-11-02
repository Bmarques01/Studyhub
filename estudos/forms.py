from django import forms

from .models import Categoria, Disciplina, Periodo, Topico

# Um ModelForm cria o formulário a partir do model: valida os campos sozinho.


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nome', 'tipo']


class PeriodoForm(forms.ModelForm):
    class Meta:
        model = Periodo
        fields = ['nome']


class DisciplinaForm(forms.ModelForm):
    class Meta:
        model = Disciplina
        fields = ['nome', 'cor']


class NotasForm(forms.ModelForm):
    class Meta:
        model = Disciplina
        fields = ['nota_ga', 'nota_gb']


class TopicoForm(forms.ModelForm):
    class Meta:
        model = Topico
        fields = ['nome']
