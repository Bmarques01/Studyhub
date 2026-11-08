"""Gerar pela ASSINATURA do Claude (o mesmo login do Claude Code), em vez da API paga por uso.

Como funciona: o Studyhub roda o programa do Claude Code em segundo plano, no "modo print"
(`claude -p`), manda o pedido pela entrada (stdin) e lê a resposta em JSON que ele devolve.
É como digitar o pedido no Claude Code, só que quem digita é o Studyhub.

- Gasta o limite do plano da Bruna (não créditos da API).
- Só funciona no computador com o Claude Code instalado e com login feito. Num site na internet
  (AWS) isso não vale: lá é a API (IA_MODO=api).
- O PDF vai para uma pasta temporária, o Claude lê de lá com a ferramenta Read e a pasta é apagada no fim.

A resposta é devolvida "com cara" da resposta da API (stop_reason, content, usage), para o resto
do gerador (ler_resposta, extrair_html...) funcionar igual nos dois modos.
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

TEMPO_MAXIMO = 20 * 60  # segundos: um guia completo de um PDF grande leva alguns minutos


class ErroDaAssinatura(Exception):
    """Mensagem já pronta para mostrar à Bruna (o gerador converte em ErroDaIA)."""


def versao(caminho):
    """'.../anthropic.claude-code-2.1.319-win32-x64/...' -> (2, 1, 319), para achar a extensão mais nova."""
    pasta = Path(caminho).parents[2].name  # anthropic.claude-code-2.1.319-win32-x64
    numeros = pasta.removeprefix('anthropic.claude-code-').split('-')[0]
    try:
        return tuple(int(n) for n in numeros.split('.'))
    except ValueError:
        return (0,)


def achar_programa():
    """Onde está o claude: o caminho do .env (CLAUDE_CAMINHO), o comando instalado ou o da extensão do VS Code."""
    escolhido = os.environ.get('CLAUDE_CAMINHO', '').strip()
    if escolhido:
        if not Path(escolhido).is_file():
            raise ErroDaAssinatura(f'O CLAUDE_CAMINHO do .env não existe: {escolhido}')
        return escolhido
    instalado = shutil.which('claude')
    if instalado:
        return instalado
    # A extensão do VS Code traz o programa junto; a pasta muda de nome a cada atualização
    padrao = str(Path.home() / '.vscode' / 'extensions' / 'anthropic.claude-code-*'
                 / 'resources' / 'native-binary' / 'claude*')
    candidatos = [c for c in glob.glob(padrao) if Path(c).is_file()]
    if candidatos:
        return max(candidatos, key=versao)
    raise ErroDaAssinatura('Não achei o Claude Code neste computador. Instale a extensão do VS Code (ou o '
                           'Claude Code de linha de comando) e faça login, ou use IA_MODO=api no .env.')


def montar_comando(programa, sistema, esquema, modelo, com_pdf):
    comando = [
        programa, '-p',                    # modo "print": responde uma vez e sai
        '--output-format', 'json',         # a resposta vem num JSON com o texto, o uso e se deu erro
        '--model', modelo,
        '--effort', 'medium',
        '--system-prompt', sistema,        # troca as instruções de programador do Claude Code pelas nossas
        '--restricted',                    # sem rodar comandos, sem internet, sem as configurações do usuário
        '--strict-mcp-config',             # sem conectores (MCP)
        '--no-session-persistence',        # não guarda a conversa no histórico do Claude Code
        # Só a leitura de arquivos (para o PDF); sem PDF, nenhuma ferramenta
        '--tools', 'Read' if com_pdf else '',
    ]
    if com_pdf:
        comando += ['--allowedTools', 'Read']
    if esquema:
        comando += ['--json-schema', json.dumps(esquema)]
    return comando


def ambiente(max_tokens):
    """As variáveis do programa: SEM a chave da API (senão ele usaria a API, e não a assinatura)."""
    variaveis = {k: v for k, v in os.environ.items() if k not in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN')}
    variaveis['CLAUDE_CODE_MAX_OUTPUT_TOKENS'] = str(max_tokens)
    return variaveis


def pedido_completo(pdf, texto, pedido):
    """texto já vem embrulhado em <material>...</material> (o mesmo bloco da API)."""
    if pdf is not None:
        return (f'O material de aula está no arquivo slides.pdf, nesta pasta. Leia o PDF inteiro com a '
                f'ferramenta Read (todas as páginas) antes de responder.\n\n{pedido}')
    return f'{texto}\n\n{pedido}'


def ler_saida(saida):
    """O JSON do Claude Code -> uma "mensagem" no formato da API."""
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError:
        raise ErroDaAssinatura('O Claude Code respondeu num formato inesperado. Tente de novo.')
    if isinstance(dados, list):  # algumas versões devolvem a lista de eventos; o resultado é o último
        dados = next((d for d in reversed(dados) if d.get('type') == 'result'), {})

    if dados.get('is_error') or dados.get('subtype') not in (None, 'success'):
        texto = str(dados.get('result') or dados.get('subtype') or '')
        baixo = texto.lower()
        if 'limit' in baixo:
            raise ErroDaAssinatura('O limite de uso da sua assinatura do Claude acabou por agora. '
                                   'Ele volta em algumas horas (ou use IA_MODO=api no .env).')
        if 'login' in baixo or 'auth' in baixo or '401' in baixo:
            raise ErroDaAssinatura('O Claude Code não está com login feito. Abra o Claude Code e entre na sua conta.')
        raise ErroDaAssinatura(f'O Claude Code deu erro: {texto[:200]}')

    if dados.get('structured_output') is not None:
        texto, parada = json.dumps(dados['structured_output'], ensure_ascii=False), 'end_turn'
    else:
        texto = dados.get('result') or ''
        parada = dados.get('stop_reason') if dados.get('stop_reason') in ('max_tokens', 'refusal') else 'end_turn'

    uso = dados.get('usage') or {}
    entrada = sum(uso.get(c, 0) or 0 for c in
                  ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
    return SimpleNamespace(
        via='assinatura',
        model=None,  # o gerador preenche com o modelo pedido
        stop_reason=parada,
        content=[SimpleNamespace(type='text', text=texto)],
        usage=SimpleNamespace(input_tokens=entrada, output_tokens=uso.get('output_tokens', 0) or 0),
    )


def pedir(*, pdf, texto, pedido, sistema, esquema, max_tokens, modelo):
    """Roda o Claude Code e devolve a resposta no formato da API."""
    programa = achar_programa()
    # Pasta temporária: é onde o Claude Code "trabalha" (e o único lugar que ele pode ler)
    with tempfile.TemporaryDirectory(prefix='studyhub-ia-') as pasta:
        if pdf is not None:
            Path(pasta, 'slides.pdf').write_bytes(pdf)
        try:
            processo = subprocess.run(
                montar_comando(programa, sistema, esquema, modelo, com_pdf=pdf is not None),
                input=pedido_completo(pdf, texto, pedido),
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                cwd=pasta, env=ambiente(max_tokens), timeout=TEMPO_MAXIMO,
            )
        except subprocess.TimeoutExpired:
            raise ErroDaAssinatura('O Claude Code demorou demais e foi interrompido. Tente com menos material.')
        except OSError as erro:
            raise ErroDaAssinatura(f'Não consegui abrir o Claude Code ({erro}).')

    if not processo.stdout.strip():
        detalhe = processo.stderr.strip()[:200] or f'código {processo.returncode}'
        raise ErroDaAssinatura(f'O Claude Code não respondeu ({detalhe}).')
    mensagem = ler_saida(processo.stdout)
    mensagem.model = modelo
    return mensagem
