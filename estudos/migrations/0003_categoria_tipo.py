# Troca "divisão" (semestres/módulos/nenhuma) por "tipo" (graduação/pós/projetos/outro).
# Os dados existentes são convertidos: semestre → graduação, módulo → pós, nenhuma → outro.
from django.db import migrations, models

DIVISAO_PARA_TIPO = {'semestre': 'graduacao', 'modulo': 'pos', '': 'outro'}
TIPO_PARA_DIVISAO = {'graduacao': 'semestre', 'pos': 'modulo'}


def converter(apps, schema_editor):
    Categoria = apps.get_model('estudos', 'Categoria')
    for categoria in Categoria.objects.all():
        categoria.tipo = DIVISAO_PARA_TIPO.get(categoria.tipo, 'outro')
        categoria.save(update_fields=['tipo'])


def desfazer(apps, schema_editor):
    Categoria = apps.get_model('estudos', 'Categoria')
    for categoria in Categoria.objects.all():
        categoria.tipo = TIPO_PARA_DIVISAO.get(categoria.tipo, '')
        categoria.save(update_fields=['tipo'])


class Migration(migrations.Migration):

    dependencies = [
        ('estudos', '0002_categorias_e_periodos'),
    ]

    operations = [
        migrations.RenameField('categoria', 'divisao', 'tipo'),
        migrations.RunPython(converter, desfazer),
        migrations.AlterField(
            model_name='categoria',
            name='tipo',
            field=models.CharField(choices=[('graduacao', 'Graduação'), ('pos', 'Pós-graduação'), ('projetos', 'Projetos'), ('outro', 'Outro')], default='outro', max_length=10),
        ),
    ]
