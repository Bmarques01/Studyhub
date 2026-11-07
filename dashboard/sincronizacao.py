"""Sincronização dos dados entre computadores por um repositório Git PRIVADO.

Como funciona:
- A pasta `dados/` (fora do Git do código) é um clone do repositório privado de dados.
- `enviar_dados`: exporta o banco para `dados/studyhub.json` (texto, que o Git entende), faz commit e push.
- `receber_dados`: puxa a versão mais nova e carrega no banco, substituindo o que havia.
- O arquivo `dados/.git/studyhub-ultima-versao` (dentro da pasta interna do Git, nunca é enviado)
  guarda qual versão este computador conhece. Assim dá para avisar quando o outro computador enviou algo que este ainda não recebeu,
  ou quando há mudanças locais que ainda não foram enviadas.
"""
import io
import json
import platform
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

APPS = ['estudos', 'pomodoro', 'dashboard', 'calendario', 'curso', 'projetos', 'cadernos', 'flashcards', 'questoes', 'ia']
ARQUIVO = 'studyhub.json'
MARCADOR = 'studyhub-ultima-versao'  # fica dentro de dados/.git/


class ErroSincronizacao(Exception):
    """Erro com uma mensagem amigável, para mostrar no terminal."""


# ===== Git =====

def pasta():
    return Path(settings.DADOS_DIR)


def git(*args, verificar=True):
    resultado = subprocess.run(['git', '-C', str(pasta()), *args], capture_output=True, text=True,
                               encoding='utf-8')
    if verificar and resultado.returncode != 0:
        raise ErroSincronizacao(f'Erro no git ({" ".join(args)}):\n{resultado.stderr.strip()}')
    return resultado.stdout.strip()


def preparar_repositorio():
    """Clona o repositório de dados na primeira vez; nas outras, só busca as novidades."""
    if not (pasta() / '.git').exists():
        pasta().parent.mkdir(parents=True, exist_ok=True)
        resultado = subprocess.run(['git', 'clone', settings.DADOS_REPO, str(pasta())],
                                   capture_output=True, text=True, encoding='utf-8')
        if resultado.returncode != 0:
            raise ErroSincronizacao(f'Não consegui clonar {settings.DADOS_REPO}:\n{resultado.stderr.strip()}')
    git('fetch', 'origin')


def versao_remota():
    """Último commit do GitHub (ou None se o repositório ainda está vazio)."""
    saida = git('ls-remote', 'origin', 'refs/heads/main', verificar=False)
    return saida.split()[0] if saida else None


def versao_conhecida():
    marcador = pasta() / '.git' / MARCADOR
    return marcador.read_text(encoding='utf-8').strip() if marcador.exists() else None


def lembrar_versao(versao):
    (pasta() / '.git' / MARCADOR).write_text(versao or '', encoding='utf-8')


# ===== Banco =====

def exportar():
    """Banco → texto JSON (sempre na mesma ordem, para o Git mostrar só o que mudou)."""
    saida = io.StringIO()
    call_command('dumpdata', *APPS, indent=2, stdout=saida)
    return saida.getvalue()


def conteudo_da_versao(versao):
    return git('show', f'{versao}:{ARQUIVO}', verificar=False) if versao else ''


def tem_mudancas_locais():
    """O banco mudou desde a última vez que este computador enviou ou recebeu?"""
    conhecida = versao_conhecida()
    if not conhecida:
        return True
    return json.loads(exportar()) != json.loads(conteudo_da_versao(conhecida) or '[]')


def banco_tem_dados():
    """Há algo além do perfil (que o dashboard cria sozinho)?"""
    return any(item['model'] != 'dashboard.perfil' for item in json.loads(exportar()))


# ===== Comandos =====

def enviar(forcar=False):
    preparar_repositorio()
    remota = versao_remota()
    if remota and remota != versao_conhecida() and not forcar:
        raise ErroSincronizacao(
            'O GitHub tem dados mais novos, enviados de outro computador, que este ainda não recebeu.\n'
            'Rode "receber_dados" primeiro. Se tiver certeza de que quer sobrescrever, use --forcar.')

    if remota:
        git('checkout', '-B', 'main', remota)
    else:
        git('checkout', '--orphan', 'main', verificar=False)  # primeiro envio: repositório vazio

    (pasta() / ARQUIVO).write_text(exportar(), encoding='utf-8')
    git('add', ARQUIVO)
    if not git('status', '--porcelain'):
        lembrar_versao(remota)
        return 'Nada para enviar: os dados do GitHub já estão iguais aos deste computador.'

    agora = timezone.localtime().strftime('%d/%m/%Y %H:%M')
    git('commit', '-m', f'Dados de {platform.node()} em {agora}')
    git('push', 'origin', 'HEAD:main')
    lembrar_versao(git('rev-parse', 'HEAD'))
    return f'Dados enviados ({agora}).'


def receber(forcar=False):
    preparar_repositorio()
    remota = versao_remota()
    if not remota:
        raise ErroSincronizacao('O repositório de dados ainda está vazio: rode "enviar_dados" no outro computador.')
    if remota == versao_conhecida() and not tem_mudancas_locais():
        return 'Já está tudo atualizado.'
    if not versao_conhecida() and banco_tem_dados() and not forcar:
        raise ErroSincronizacao(
            'Este computador já tem dados que nunca foram sincronizados e seriam substituídos.\n'
            'Se quiser mesmo trocar pelos dados do GitHub, use --forcar.')
    if versao_conhecida() and tem_mudancas_locais() and not forcar:
        raise ErroSincronizacao(
            'Este computador tem mudanças que ainda não foram enviadas e seriam perdidas.\n'
            'Rode "enviar_dados" antes. Se quiser descartar as mudanças locais, use --forcar.')

    git('checkout', '-B', 'main', remota)
    arquivo = pasta() / ARQUIVO
    with transaction.atomic():  # tudo ou nada: se der erro, o banco fica como estava
        apagar_dados()
        call_command('loaddata', str(arquivo), verbosity=0)
    lembrar_versao(remota)
    return 'Dados recebidos e carregados.'


def apagar_dados():
    """Apaga os dados dos apps (do mais "dependente" para o mais "básico")."""
    from django.apps import apps
    for app in reversed(APPS):
        for modelo in reversed(list(apps.get_app_config(app).get_models())):
            modelo.objects.all().delete()
