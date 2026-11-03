from django import forms

from estudos.models import Disciplina, Topico

from .models import Flashcard


def conferir_topico(form, disciplina):
    """O tópico (opcional) precisa ser da disciplina escolhida."""
    topico = form.cleaned_data.get('topico')
    if topico and disciplina and topico.disciplina_id != disciplina.id:
        raise forms.ValidationError('O tópico escolhido não é dessa disciplina.')
    return topico


class FlashcardForm(forms.ModelForm):
    class Meta:
        model = Flashcard
        fields = ['disciplina', 'topico', 'frente', 'verso']

    def clean_topico(self):
        return conferir_topico(self, self.cleaned_data.get('disciplina'))


class EdicaoForm(forms.ModelForm):
    """Editar um cartão: a disciplina fica a mesma (a memória do cartão continua)."""

    class Meta:
        model = Flashcard
        fields = ['topico', 'frente', 'verso']

    def clean_topico(self):
        return conferir_topico(self, self.instance.disciplina)


class ImportarForm(forms.Form):
    """Colar vários cartões de uma vez (formato F: / V:, ver importacao.py)."""

    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all())
    topico = forms.ModelChoiceField(queryset=Topico.objects.all(), required=False)
    texto = forms.CharField()

    def clean_topico(self):
        return conferir_topico(self, self.cleaned_data.get('disciplina'))


class BaralhoForm(forms.Form):
    """Baralho novo = tópico novo na disciplina."""

    disciplina = forms.ModelChoiceField(queryset=Disciplina.objects.all())
    nome = forms.CharField(max_length=150)

    def clean_nome(self):
        nome = self.cleaned_data['nome'].strip()
        if not nome:
            raise forms.ValidationError('Dê um nome ao baralho.')
        return nome
