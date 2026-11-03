from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

# Apps com os seus dados (o resto, como sessões e permissões, o Django recria sozinho)
APPS = ['estudos', 'pomodoro', 'dashboard', 'calendario', 'curso', 'projetos', 'cadernos']


class Command(BaseCommand):
    help = ('Salva todos os seus dados num arquivo JSON (pasta backup/), para levar a outro computador. '
            'Para restaurar: python manage.py loaddata backup/ARQUIVO.json')

    def handle(self, *args, **opcoes):
        pasta = Path(settings.BASE_DIR) / 'backup'
        pasta.mkdir(exist_ok=True)
        arquivo = pasta / f'studyhub-{timezone.localdate():%Y-%m-%d}.json'
        with open(arquivo, 'w', encoding='utf-8') as saida:
            call_command('dumpdata', *APPS, indent=2, stdout=saida)
        self.stdout.write(self.style.SUCCESS(f'Backup salvo em {arquivo}'))
