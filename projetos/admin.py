from django.contrib import admin

from .models import EntradaDiario, Funcionalidade, Projeto, Tarefa


class TarefaInline(admin.TabularInline):
    model = Tarefa
    extra = 0


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'status', 'tecnologias']


@admin.register(Funcionalidade)
class FuncionalidadeAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'projeto', 'tipo', 'prioridade', 'status']
    list_filter = ['projeto', 'status', 'tipo', 'prioridade']
    inlines = [TarefaInline]


admin.site.register(EntradaDiario)
