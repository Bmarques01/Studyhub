from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from estudos.models import Categoria, Disciplina, Periodo


class Grade(models.Model):
    """A grade curricular de um curso (ex.: Ciência da Computação na Unisinos).
    Fica ligada a uma categoria de Estudos do tipo graduação."""

    nome = models.CharField(max_length=150)
    instituicao = models.CharField(max_length=100, blank=True)
    categoria = models.OneToOneField(Categoria, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='grade')
    # Optativas e transversais: o aluno escolhe entre várias, até completar estas horas
    horas_optativas = models.PositiveIntegerField(default=0)
    horas_transversais = models.PositiveIntegerField(default=0)
    horas_complementares = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nome


class DisciplinaGrade(models.Model):
    """Uma disciplina da grade, com a sua situação (concluída, cursando...)."""

    BLOCOS = [
        ('obrigatoria', 'Obrigatória'),
        ('optativa', 'Optativa'),
        ('transversal', 'Transversal'),
    ]
    SITUACOES = [
        ('nao_cursada', 'Não cursada'),
        ('cursando', 'Cursando'),
        ('concluida', 'Concluída'),
        ('compensada', 'Compensada'),
        ('reprovada', 'Reprovada'),
    ]
    FEITAS = ('concluida', 'compensada')  # contam como cumpridas (para horas e pré-requisitos)

    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='disciplinas')
    codigo = models.CharField(max_length=10)
    nome = models.CharField(max_length=150)
    carga_horaria = models.PositiveIntegerField()
    semestre = models.PositiveSmallIntegerField(null=True, blank=True)  # vazio para optativas/transversais
    bloco = models.CharField(max_length=12, choices=BLOCOS, default='obrigatoria')
    # symmetrical=False: "A exige B" não quer dizer "B exige A"
    pre_requisitos = models.ManyToManyField('self', symmetrical=False, blank=True,
                                            related_name='libera')

    situacao = models.CharField(max_length=12, choices=SITUACOES, default='nao_cursada')
    semestre_cursado = models.CharField(max_length=7, blank=True)  # ex.: 2026/2
    nota_final = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                     validators=[MinValueValidator(0), MaxValueValidator(10)])
    # A disciplina correspondente em Estudos (tópicos, pomodoro, notas GA/GB...)
    disciplina = models.OneToOneField(Disciplina, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='na_grade')

    class Meta:
        ordering = ['semestre', 'codigo']
        unique_together = [('grade', 'codigo')]
        verbose_name = 'disciplina da grade'
        verbose_name_plural = 'disciplinas da grade'

    def __str__(self):
        return f'{self.codigo} {self.nome}'

    @property
    def feita(self):
        return self.situacao in self.FEITAS

    def pre_requisitos_pendentes(self):
        """Pré-requisitos que ainda não foram cumpridos."""
        return [p for p in self.pre_requisitos.all() if not p.feita]

    @property
    def liberada(self):
        """Pode ser cursada agora: ainda não foi feita e todos os pré-requisitos estão cumpridos."""
        return self.situacao in ('nao_cursada', 'reprovada') and not self.pre_requisitos_pendentes()

    def ligar_aos_estudos(self):
        """Ao marcar como 'cursando': cria (ou reaproveita) a disciplina em Estudos,
        no semestre letivo atual, para usar tópicos, pomodoro, notas e calendário."""
        categoria = self.grade.categoria
        if self.disciplina_id or categoria is None:
            return self.disciplina
        periodo = Periodo.letivo_atual(categoria)
        self.disciplina = Disciplina.objects.create(categoria=categoria, periodo=periodo, nome=self.nome)
        self.save(update_fields=['disciplina'])
        return self.disciplina
