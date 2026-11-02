from django.contrib import admin

from .models import DisciplinaGrade, Grade


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['nome', 'instituicao', 'categoria']


@admin.register(DisciplinaGrade)
class DisciplinaGradeAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'semestre', 'bloco', 'carga_horaria', 'situacao']
    list_filter = ['bloco', 'situacao', 'semestre']
    search_fields = ['codigo', 'nome']
    filter_horizontal = ['pre_requisitos']
