from django.db import models
from django.utils import timezone

from estudos.models import Disciplina, Topico


class Questao(models.Model):
    """Uma questão do banco. A resposta certa depende do tipo:
    múltipla escolha → a alternativa marcada como correta; V/F → "V" ou "F" em `resposta`;
    aberta → o texto esperado em `resposta` (você mesma confere se acertou)."""

    TIPOS = [
        ('multipla', 'múltipla escolha'),
        ('vf', 'verdadeiro ou falso'),
        ('aberta', 'aberta'),
    ]

    disciplina = models.ForeignKey(Disciplina, on_delete=models.CASCADE, related_name='questoes')
    topico = models.ForeignKey(Topico, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='questoes')
    tipo = models.CharField(max_length=10, choices=TIPOS, default='multipla')
    enunciado = models.TextField()
    resposta = models.TextField(blank=True)
    explicacao = models.TextField(blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criada_em', 'id']
        verbose_name = 'questão'
        verbose_name_plural = 'questões'

    def __str__(self):
        return self.enunciado[:60]

    def texto_da_resposta(self):
        """A resposta certa escrita por extenso, para mostrar depois de responder."""
        if self.tipo == 'vf':
            return 'Verdadeiro' if self.resposta == 'V' else 'Falso'
        if self.tipo == 'aberta':
            return self.resposta
        certa = next((a for a in self.alternativas.all() if a.correta), None)
        return f'{certa.letra}) {certa.texto}' if certa else ''


class Alternativa(models.Model):
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, related_name='alternativas')
    texto = models.TextField()
    correta = models.BooleanField(default=False)
    ordem = models.PositiveSmallIntegerField(default=0)  # 0 = A, 1 = B...

    class Meta:
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.letra}) {self.texto[:40]}'

    @property
    def letra(self):
        return chr(ord('A') + self.ordem)


class Questionario(models.Model):
    """Uma rodada de questões: quais caíram (na ordem) e as respostas dadas."""

    disciplina = models.ForeignKey(Disciplina, on_delete=models.CASCADE, related_name='questionarios')
    topico = models.ForeignKey(Topico, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='questionarios')
    questoes = models.JSONField(default=list)  # ids das questões, na ordem em que aparecem
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']

    def __str__(self):
        return f'{self.disciplina} · {timezone.localtime(self.criado_em):%d/%m %H:%M}'


class Resposta(models.Model):
    """Cada resposta dada. Guarda o histórico (o caderno de erros vai partir daqui)."""

    questionario = models.ForeignKey(Questionario, on_delete=models.CASCADE, null=True, blank=True,
                                     related_name='respostas')
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, related_name='respostas')
    resposta_dada = models.TextField(blank=True)  # a letra, "V"/"F" ou o texto escrito
    acertou = models.BooleanField()
    respondida_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['respondida_em', 'id']

    def __str__(self):
        return f'{self.questao} · {"acertou" if self.acertou else "errou"}'
