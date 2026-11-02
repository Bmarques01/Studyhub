from django.core.validators import RegexValidator
from django.db import models

validar_cor = RegexValidator(r'^#[0-9a-fA-F]{6}$', 'Use uma cor no formato #rrggbb.')


class Categoria(models.Model):
    """Nível mais alto: ex. Ciência da Computação, Cloud Computing, Estudos livres."""

    # choices = lista fechada de opções: (valor salvo no banco, texto mostrado na tela)
    DIVISOES = [
        ('semestre', 'Semestres'),
        ('modulo', 'Módulos'),
        ('', 'Sem divisão'),
    ]

    nome = models.CharField(max_length=100)
    divisao = models.CharField(max_length=10, choices=DIVISOES, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em']

    def __str__(self):
        return self.nome

    @property
    def nome_periodo(self):
        """Como chamar cada período desta categoria: 'semestre', 'módulo' ou ''."""
        return {'semestre': 'semestre', 'modulo': 'módulo'}.get(self.divisao, '')


class Periodo(models.Model):
    """Um semestre ou módulo dentro de uma categoria. Ex.: 5º semestre, Módulo 2."""

    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='periodos')
    nome = models.CharField(max_length=100)
    ordem = models.PositiveIntegerField(default=0)  # define a ordem na tela

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'período'

    def __str__(self):
        return f'{self.categoria} · {self.nome}'


class Disciplina(models.Model):
    """Ex.: Redes 2, Kubernetes. Pertence a uma categoria e, opcionalmente, a um período."""

    # ForeignKey = "pertence a". on_delete=CASCADE: apagar a categoria apaga as disciplinas dela.
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='disciplinas')
    # SET_NULL: apagar o período não apaga a disciplina, ela só fica "sem período"
    periodo = models.ForeignKey(Periodo, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='disciplinas')
    nome = models.CharField(max_length=100)
    cor = models.CharField(max_length=7, default='#e0609a', validators=[validar_cor])
    arquivada = models.BooleanField(default=False)  # some das listas, mas o histórico fica
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Topico(models.Model):
    """Ex.: Serviços de Enlace. Pertence a uma disciplina."""

    disciplina = models.ForeignKey(Disciplina, on_delete=models.CASCADE, related_name='topicos')
    nome = models.CharField(max_length=150)

    class Meta:
        ordering = ['nome']
        verbose_name = 'tópico'

    def __str__(self):
        return self.nome
