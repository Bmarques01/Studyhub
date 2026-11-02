from django.contrib import admin

from .models import Caderno, Pagina


@admin.register(Caderno)
class CadernoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'disciplina', 'papel', 'fonte', 'atualizado_em']


@admin.register(Pagina)
class PaginaAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'caderno', 'topico', 'atualizada_em']
    search_fields = ['titulo', 'texto']
