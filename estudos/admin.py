from django.contrib import admin

from .models import Categoria, Disciplina, Periodo, Topico

admin.site.register(Categoria)
admin.site.register(Periodo)
admin.site.register(Disciplina)
admin.site.register(Topico)
