from django.db import models
from django.utils import timezone

from estudos.models import Disciplina


class Evento(models.Model):
    """Uma prova, trabalho, entrega ou outro compromisso com data."""

    TIPOS = [
        ('prova', 'Prova'),
        ('trabalho', 'Trabalho'),
        ('entrega', 'Entrega'),
        ('outro', 'Outro'),
    ]

    titulo = models.CharField(max_length=150)
    tipo = models.CharField(max_length=10, choices=TIPOS, default='prova')
    data = models.DateField()
    hora = models.TimeField(null=True, blank=True)  # opcional
    disciplina = models.ForeignKey(Disciplina, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='eventos')
    descricao = models.TextField(blank=True)
    concluido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        # sem hora vem antes; depois por horário
        ordering = ['data', models.F('hora').asc(nulls_first=True), 'id']

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.titulo} ({self.data:%d/%m})'

    @property
    def dias_restantes(self):
        return (self.data - timezone.localdate()).days

    @property
    def quando(self):
        """Texto amigável: 'hoje', 'amanhã', 'em 9 dias', 'há 3 dias'."""
        dias = self.dias_restantes
        if dias == 0:
            return 'hoje'
        if dias == 1:
            return 'amanhã'
        if dias == -1:
            return 'ontem'
        return f'em {dias} dias' if dias > 0 else f'há {-dias} dias'
