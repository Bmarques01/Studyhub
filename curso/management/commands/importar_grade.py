from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from curso.grade_cc_unisinos import DISCIPLINAS, GRADE
from curso.models import DisciplinaGrade, Grade
from estudos.models import Categoria


class Command(BaseCommand):
    help = 'Importa a grade de Ciência da Computação (Unisinos). Pode rodar de novo: não duplica nem apaga situações.'

    def add_arguments(self, parser):
        parser.add_argument('--categoria', type=int, help='id da categoria de Estudos (graduação) a ligar')

    @transaction.atomic  # tudo ou nada: se der erro no meio, nada fica pela metade
    def handle(self, *args, **opcoes):
        categoria = None
        if opcoes['categoria']:
            categoria = Categoria.objects.filter(id=opcoes['categoria']).first()
            if categoria is None:
                raise CommandError('Categoria não encontrada.')

        grade, criada = Grade.objects.get_or_create(nome=GRADE['nome'], defaults=GRADE)
        if categoria:
            grade.categoria = categoria
            grade.save()

        por_codigo = {}
        for codigo, nome, horas, semestre, bloco, _ in DISCIPLINAS:
            disciplina, _ = DisciplinaGrade.objects.update_or_create(
                grade=grade, codigo=codigo,
                defaults={'nome': nome, 'carga_horaria': horas, 'semestre': semestre, 'bloco': bloco},
            )
            por_codigo[codigo] = disciplina

        for codigo, *_, requisitos in DISCIPLINAS:
            por_codigo[codigo].pre_requisitos.set([por_codigo[r] for r in requisitos])

        self.stdout.write(self.style.SUCCESS(
            f'{"Criada" if criada else "Atualizada"}: {grade} com {len(por_codigo)} disciplinas.'))
