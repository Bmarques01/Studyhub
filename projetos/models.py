from django.db import models
from django.db.models import Sum
from django.utils import timezone

from estudos.models import validar_cor


class Projeto(models.Model):
    """Um projeto de programação (ex.: Studyhub)."""

    STATUS = [
        ('ideia', 'Ideia'),
        ('ativo', 'Ativo'),
        ('pausado', 'Pausado'),
        ('concluido', 'Concluído'),
    ]
    TIPOS = [
        ('pessoal', 'Pessoal'),
        ('trabalho', 'Trabalho'),
    ]

    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='ativo')
    tipo = models.CharField(max_length=10, choices=TIPOS, default='pessoal')
    data_inicio = models.DateField('início', null=True, blank=True)
    data_fim = models.DateField('fim', null=True, blank=True)  # vazio = ainda em andamento
    cor = models.CharField(max_length=7, default='#a77bf3', validators=[validar_cor])
    # Tecnologias separadas por vírgula: "Python, Django, JavaScript"
    tecnologias = models.CharField(max_length=300, blank=True)
    link_repositorio = models.URLField(blank=True)
    link_deploy = models.URLField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em']

    def __str__(self):
        return self.nome

    @property
    def lista_tecnologias(self):
        return [t.strip() for t in self.tecnologias.split(',') if t.strip()]

    @property
    def dias(self):
        """Quantos dias o projeto durou (ou dura até hoje, se ainda não terminou). None sem data de início."""
        if not self.data_inicio:
            return None
        fim = min(self.data_fim or timezone.localdate(), timezone.localdate())
        return max(0, (fim - self.data_inicio).days + 1)


class Funcionalidade(models.Model):
    """Um cartão do Kanban: uma funcionalidade, bug, melhoria ou refatoração."""

    STATUS = [
        ('backlog', 'Backlog'),
        ('a_fazer', 'A fazer'),
        ('fazendo', 'Fazendo'),
        ('feito', 'Feito'),
    ]
    TIPOS = [
        ('funcionalidade', 'Funcionalidade'),
        ('bug', 'Bug'),
        ('melhoria', 'Melhoria'),
        ('refatoracao', 'Refatoração'),
    ]
    PRIORIDADES = [
        ('alta', 'Alta'),
        ('media', 'Média'),
        ('baixa', 'Baixa'),
    ]

    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='funcionalidades')
    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=15, choices=TIPOS, default='funcionalidade')
    prioridade = models.CharField(max_length=5, choices=PRIORIDADES, default='media')
    status = models.CharField(max_length=10, choices=STATUS, default='a_fazer')
    ordem = models.PositiveIntegerField(default=0)  # posição dentro da coluna do Kanban
    estimativa_horas = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    concluida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['ordem', 'id']

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        # guarda quando foi concluída (e limpa se voltar para outra coluna)
        if self.status == 'feito' and self.concluida_em is None:
            self.concluida_em = timezone.now()
        elif self.status != 'feito':
            self.concluida_em = None
        super().save(*args, **kwargs)

    @property
    def minutos_trabalhados(self):
        return self.sessoes.aggregate(total=Sum('duracao_minutos'))['total'] or 0


class Tarefa(models.Model):
    """Um item do checklist de uma funcionalidade."""

    funcionalidade = models.ForeignKey(Funcionalidade, on_delete=models.CASCADE, related_name='tarefas')
    texto = models.CharField(max_length=200)
    feita = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['feita', 'criada_em']

    def __str__(self):
        return self.texto


class EntradaDiario(models.Model):
    """Diário de bordo (devlog): o que fiz, o que aprendi, onde travei."""

    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='diario')
    data = models.DateField(default=timezone.localdate)
    fiz = models.TextField('o que fiz', blank=True)
    aprendi = models.TextField('o que aprendi', blank=True)
    travei = models.TextField('onde travei', blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data', '-criada_em']
        verbose_name = 'entrada do diário'
        verbose_name_plural = 'diário de bordo'

    def __str__(self):
        return f'{self.projeto} · {self.data:%d/%m/%Y}'
