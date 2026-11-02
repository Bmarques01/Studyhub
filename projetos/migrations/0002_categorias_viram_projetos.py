# Antes, projetos eram categorias de Estudos do tipo "projetos".
# Agora têm página própria: cada uma dessas categorias vira um Projeto.
# Se a categoria tinha disciplinas, ela é mantida (como "outro") para não perder nada.
from django.db import migrations


def converter(apps, schema_editor):
    Categoria = apps.get_model('estudos', 'Categoria')
    Projeto = apps.get_model('projetos', 'Projeto')
    for categoria in Categoria.objects.filter(tipo='projetos'):
        Projeto.objects.create(nome=categoria.nome, status='ativo')
        if categoria.disciplinas.exists():
            categoria.tipo = 'outro'
            categoria.save()
        else:
            categoria.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('projetos', '0001_initial'),
        ('estudos', '0005_alter_categoria_tipo'),
    ]

    operations = [
        migrations.RunPython(converter, migrations.RunPython.noop),
    ]
