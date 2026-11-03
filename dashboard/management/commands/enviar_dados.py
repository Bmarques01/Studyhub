from django.core.management.base import BaseCommand, CommandError

from dashboard.sincronizacao import ErroSincronizacao, enviar


class Command(BaseCommand):
    help = 'Envia os seus dados para o repositório privado no GitHub (use ao terminar de estudar).'

    def add_arguments(self, parser):
        parser.add_argument('--forcar', action='store_true', help='Envia mesmo se o GitHub tiver dados mais novos.')

    def handle(self, *args, **opcoes):
        try:
            self.stdout.write(self.style.SUCCESS(enviar(forcar=opcoes['forcar'])))
        except ErroSincronizacao as erro:
            raise CommandError(str(erro))
