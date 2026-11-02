from django.db import models

from estudos.models import Disciplina, Topico


class SessaoPomodoro(models.Model):
    """Um bloco de foco concluído. Cada objeto vira uma linha no banco de dados."""

    duracao_minutos = models.PositiveIntegerField()
    # SET_NULL: se a disciplina for excluída, a sessão continua existindo (só perde o vínculo)
    disciplina = models.ForeignKey(Disciplina, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='sessoes')
    topico = models.ForeignKey(Topico, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='sessoes')
    tarefa = models.CharField(max_length=200, blank=True)  # opcional: "no que você focou"
    concluida_em = models.DateTimeField(auto_now_add=True)  # preenchido automaticamente

    class Meta:
        ordering = ['-concluida_em']  # mais recentes primeiro
        verbose_name = 'sessão de pomodoro'
        verbose_name_plural = 'sessões de pomodoro'

    def __str__(self):
        return f'{self.duracao_minutos} min - {self.tarefa or "sem tarefa"}'
