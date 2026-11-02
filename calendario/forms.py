from django import forms

from .models import Evento


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ['titulo', 'tipo', 'data', 'hora', 'disciplina', 'descricao']
