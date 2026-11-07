from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from cadernos.models import Pagina
from estudos.models import Disciplina, Topico


class Geracao(models.Model):
    """Um pedido feito ao Claude: o que gerou, quanto custou e o que já foi salvo.

    Dois tipos: questões/flashcards (revisados antes de salvar) ou resumo no caderno
    (vira direto uma página de material, guardada em "pagina").

    O material enviado (PDF/texto) NÃO fica guardado: só o nome dele.
    O texto gerado fica aqui até ela revisar e salvar (no formato da importação).
    """

    TIPOS = [
        ('questoes', 'Questões e flashcards'),
        ('resumo', 'Resumo no caderno'),
    ]

    tipo = models.CharField(max_length=10, choices=TIPOS, default='questoes')
    criada_em = models.DateTimeField(auto_now_add=True)
    disciplina = models.ForeignKey(Disciplina, on_delete=models.SET_NULL, null=True, related_name='geracoes')
    topico = models.ForeignKey(Topico, on_delete=models.SET_NULL, null=True, blank=True, related_name='geracoes')
    material = models.CharField(max_length=200)  # nome do arquivo ou "texto colado"
    pedido_extra = models.TextField(blank=True)
    pediu_questoes = models.PositiveSmallIntegerField(default=0)
    pediu_flashcards = models.PositiveSmallIntegerField(default=0)

    # O que a API devolveu (para o histórico de custos)
    modelo = models.CharField(max_length=60, blank=True)
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_saida = models.PositiveIntegerField(default=0)
    custo = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0'))  # em dólares
    erro = models.CharField(max_length=300, blank=True)  # quando a IA respondeu, mas não deu certo

    # Texto gerado (editável na revisão) e quantos itens ela já salvou (0 = ainda não salvou)
    texto_questoes = models.TextField(blank=True)
    texto_flashcards = models.TextField(blank=True)
    questoes_salvas = models.PositiveSmallIntegerField(default=0)
    flashcards_salvos = models.PositiveSmallIntegerField(default=0)
    # Resumo: a página de material criada no caderno
    pagina = models.ForeignKey(Pagina, on_delete=models.SET_NULL, null=True, blank=True, related_name='geracoes')

    class Meta:
        ordering = ['-criada_em', '-id']
        verbose_name = 'geração com IA'
        verbose_name_plural = 'gerações com IA'

    def __str__(self):
        return f'{self.material} ({self.criada_em:%d/%m/%Y})'


def custo_do_mes(hoje=None):
    """(total em dólares, quantas gerações) do mês atual."""
    hoje = hoje or timezone.localdate()
    do_mes = Geracao.objects.filter(criada_em__year=hoje.year, criada_em__month=hoje.month)
    total = do_mes.aggregate(total=Sum('custo'))['total'] or Decimal('0')
    return total, do_mes.count()
