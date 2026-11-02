# Migração escrita à mão: renomeia "Curso" para "Categoria" mantendo os dados
# (o Django sozinho apagaria a tabela antiga e criaria outra vazia).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estudos', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel('Curso', 'Categoria'),
        migrations.RenameField('disciplina', 'curso', 'categoria'),
        migrations.AddField(
            model_name='categoria',
            name='divisao',
            field=models.CharField(blank=True, choices=[('semestre', 'Semestres'), ('modulo', 'Módulos'), ('', 'Sem divisão')], default='', max_length=10),
        ),
        migrations.CreateModel(
            name='Periodo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('ordem', models.PositiveIntegerField(default=0)),
                ('categoria', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='periodos', to='estudos.categoria')),
            ],
            options={
                'verbose_name': 'período',
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.AddField(
            model_name='disciplina',
            name='periodo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='disciplinas', to='estudos.periodo'),
        ),
    ]
