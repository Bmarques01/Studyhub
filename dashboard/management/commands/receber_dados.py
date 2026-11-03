from django.core.management.base import BaseCommand, CommandError

from dashboard.sincronizacao import ErroSincronizacao, receber


class Command(BaseCommand):
    help = 'Baixa os dados mais novos do repositório privado no GitHub (use ao sentar em outro computador).'

    def add_arguments(self, parser):
        parser.add_argument('--forcar', action='store_true', help='Descarta mudanças locais que não foram enviadas.')

    def handle(self, *args, **opcoes):
        try:
            self.stdout.write(self.style.SUCCESS(receber(forcar=opcoes['forcar'])))
        except ErroSincronizacao as erro:
            raise CommandError(str(erro))
