from django import forms

from .models import Caderno


class NovoCadernoForm(forms.ModelForm):
    class Meta:
        model = Caderno
        fields = ['nome', 'disciplina', 'cor_capa']


class CadernoForm(forms.ModelForm):
    class Meta:
        model = Caderno
        fields = ['nome', 'disciplina', 'cor_capa', 'papel', 'fonte', 'cor_destaque', 'cor_titulos']
