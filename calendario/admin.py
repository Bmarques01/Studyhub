from django.contrib import admin

from .models import Evento


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ['data', 'tipo', 'titulo', 'disciplina', 'concluido']
    list_filter = ['tipo', 'concluido']
