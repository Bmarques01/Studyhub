# Questionário passa de "um tópico" para "vários tópicos".
# Ordem: cria o campo novo, copia o tópico antigo para ele e só então apaga o antigo.

from django.db import migrations, models


def copiar_topico(apps, schema_editor):
    Questionario = apps.get_model('questoes', 'Questionario')
    for questionario in Questionario.objects.exclude(topico=None):
        questionario.topicos.add(questionario.topico_id)


class Migration(migrations.Migration):

    dependencies = [
        ('estudos', '0005_alter_categoria_tipo'),
        ('questoes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionario',
            name='sem_topico',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='questionario',
            name='topicos',
            field=models.ManyToManyField(blank=True, related_name='questionarios', to='estudos.topico'),
        ),
        migrations.RunPython(copiar_topico, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='questionario',
            name='topico',
        ),
    ]
