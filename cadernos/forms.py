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


MATERIAL_MAXIMO = 2_000_000  # ~2 MB de HTML (o guia de Redes tem ~100 KB)


class MaterialForm(forms.Form):
    """Material novo: cole o HTML OU envie o arquivo .html (um dos dois)."""

    titulo = forms.CharField(max_length=150, required=False)
    html = forms.CharField(required=False, strip=False)
    arquivo = forms.FileField(required=False)

    def clean(self):
        dados = super().clean()
        colado, arquivo = dados.get('html', ''), dados.get('arquivo')
        if colado.strip() and arquivo:
            raise forms.ValidationError('Cole o HTML ou envie um arquivo, não os dois.')
        if arquivo:
            if arquivo.size > MATERIAL_MAXIMO:
                raise forms.ValidationError('O arquivo passa de 2 MB.')
            bruto = arquivo.read()
            try:
                colado = bruto.decode('utf-8-sig')  # utf-8-sig: ignora o BOM, se houver
            except UnicodeDecodeError:
                colado = bruto.decode('latin-1')
        if not colado.strip():
            raise forms.ValidationError('Cole o HTML do material ou escolha um arquivo .html.')
        if len(colado) > MATERIAL_MAXIMO:
            raise forms.ValidationError('O material passa de 2 MB.')
        if '<' not in colado:
            raise forms.ValidationError('Isso não parece HTML (não tem nenhuma tag, como <h1>).')
        dados['html'] = colado
        return dados
