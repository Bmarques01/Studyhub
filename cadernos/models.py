from django.db import models

from estudos.models import Disciplina, Topico, validar_cor


class Caderno(models.Model):
    """Um caderno digital, com o visual que você escolher. Pode ou não ser de uma disciplina."""

    PAPEIS = [
        ('liso', 'Liso'),
        ('pautado', 'Pautado'),
        ('quadriculado', 'Quadriculado'),
        ('pontilhado', 'Pontilhado'),
    ]
    # (valor salvo, nome mostrado). O valor vira a classe CSS da fonte.
    FONTES = [
        ('moderna', 'Moderna (Space Grotesk)'),
        ('arredondada', 'Arredondada (Nunito)'),
        ('livro', 'Livro (Lora)'),
        ('manuscrita', 'Manuscrita (Caveat)'),
        ('escolar', 'Escolar (Patrick Hand)'),
        ('codigo', 'Código (JetBrains Mono)'),
    ]

    nome = models.CharField(max_length=100)
    disciplina = models.ForeignKey(Disciplina, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='cadernos')
    cor_capa = models.CharField(max_length=7, default='#e0609a', validators=[validar_cor])
    papel = models.CharField(max_length=12, choices=PAPEIS, default='pautado')
    fonte = models.CharField(max_length=12, choices=FONTES, default='moderna')
    cor_destaque = models.CharField(max_length=7, default='#ffd6e7', validators=[validar_cor])  # marca-texto
    cor_titulos = models.CharField(max_length=7, default='#c2417f', validators=[validar_cor])
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em']

    def __str__(self):
        return self.nome


class Pagina(models.Model):
    """Uma página do caderno. O conteúdo fica no formato do editor (Quill "Delta", em JSON):
    é reaberto exatamente como foi escrito e nunca vira código na página."""

    caderno = models.ForeignKey(Caderno, on_delete=models.CASCADE, related_name='paginas')
    titulo = models.CharField(max_length=150, default='Sem título')
    topico = models.ForeignKey(Topico, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='paginas')
    conteudo = models.JSONField(default=dict, blank=True)
    texto = models.TextField(blank=True)  # só o texto, para a prévia e para buscas
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['criada_em', 'id']
        verbose_name = 'página'

    def __str__(self):
        return self.titulo
