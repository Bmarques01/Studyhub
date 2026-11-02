from django.contrib import admin

from .models import SessaoPomodoro


@admin.register(SessaoPomodoro)
class SessaoPomodoroAdmin(admin.ModelAdmin):
    list_display = ['concluida_em', 'duracao_minutos', 'tarefa']
