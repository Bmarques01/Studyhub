from django.db import models
from django.utils import timezone

from estudos.models import Disciplina, Topico


class Flashcard(models.Model):
    """Um cartão: pergunta na frente, resposta no verso.

    Os campos de "memória" são os que o FSRS (o algoritmo de repetição espaçada) usa para
    decidir quando o cartão volta. Quem preenche é o arquivo memoria.py, a cada resposta.
    """

    # Mesmos números que a biblioteca fsrs usa para os estados
    ESTADOS = [
        (1, 'aprendendo'),     # novo ou recém-visto: volta em minutos
        (2, 'revisão'),        # já "aprendido": volta em dias
        (3, 'reaprendendo'),   # era revisão, mas você esqueceu
    ]

    disciplina = models.ForeignKey(Disciplina, on_delete=models.CASCADE, related_name='flashcards')
    topico = models.ForeignKey(Topico, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='flashcards')
    frente = models.TextField()
    verso = models.TextField()

    # --- memória (FSRS) ---
    estado = models.PositiveSmallIntegerField(choices=ESTADOS, default=1)
    passo = models.PositiveSmallIntegerField(null=True, blank=True, default=0)  # etapa da aprendizagem
    estabilidade = models.FloatField(null=True, blank=True)  # quantos dias a lembrança "aguenta"
    dificuldade = models.FloatField(null=True, blank=True)   # de 1 (fácil) a 10 (difícil)
    vencimento = models.DateTimeField(null=True, blank=True)       # quando deve ser revisado
    ultima_revisao = models.DateTimeField(null=True, blank=True)
    primeira_revisao = models.DateTimeField(null=True, blank=True)  # vazio = cartão novo
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em', 'id']

    def __str__(self):
        return self.frente[:60]

    @property
    def novo(self):
        return self.primeira_revisao is None


class Revisao(models.Model):
    """Cada resposta dada a um cartão. Guarda o histórico (serve para estatísticas no futuro)."""

    NOTAS = [
        (1, 'de novo'),
        (2, 'difícil'),
        (3, 'bom'),
        (4, 'fácil'),
    ]

    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name='revisoes')
    nota = models.PositiveSmallIntegerField(choices=NOTAS)
    revisada_em = models.DateTimeField(default=timezone.now)
    duracao_segundos = models.PositiveIntegerField(null=True, blank=True)  # tempo até responder

    class Meta:
        ordering = ['-revisada_em']
        verbose_name = 'revisão'
        verbose_name_plural = 'revisões'

    def __str__(self):
        return f'{self.get_nota_display()} · {self.flashcard}'
