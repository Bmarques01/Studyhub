from django.contrib import admin

from .models import Alternativa, Questao, Questionario, Resposta

admin.site.register(Questao)
admin.site.register(Alternativa)
admin.site.register(Questionario)
admin.site.register(Resposta)
