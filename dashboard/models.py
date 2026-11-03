from django.db import models


class Perfil(models.Model):
    """Suas preferências. Como o site é só seu, existe uma única linha (id=1)."""

    nome = models.CharField(max_length=60, default='Bruna')
    meta_semanal_horas = models.PositiveSmallIntegerField(default=10)
    # quantos cartões novos de flashcards entram na revisão por dia (os vencidos não têm limite)
    flashcards_novos_por_dia = models.PositiveSmallIntegerField(default=20)

    class Meta:
        verbose_name_plural = 'perfil'

    def __str__(self):
        return self.nome

    @classmethod
    def atual(cls):
        """Busca o perfil; se ainda não existir, cria com os valores padrão."""
        perfil, _ = cls.objects.get_or_create(pk=1)
        return perfil
