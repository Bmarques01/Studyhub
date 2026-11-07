# Studyhub — guia para o Claude

Plataforma pessoal de estudos da **Bruna** (Django + JavaScript puro + SQLite), feita para uso local,
só por ela. Repositório: https://github.com/Bmarques01/Studyhub

## Quem é a usuária e como trabalhar com ela

- Bruna cursa **Ciência da Computação na Unisinos** e faz **pós em Cloud Computing**. É **iniciante em
  programação**: o projeto também é para ela aprender. Converse em **português**, com linguagem simples,
  e explique o "porquê" das decisões técnicas sem jargão desnecessário.
- Ela decide o produto. Para funcionalidades grandes, **proponha antes de codar** (com um esboço e 2 a 4
  perguntas objetivas, com uma recomendação). Para ajustes pequenos e pedidos claros, faça direto.
- **Depois de cada entrega:** rodar os testes, fazer commit (mensagem em português) e `git push`.
  Lembrar a Bruna de dar **Ctrl + F5** (o navegador guarda CSS/JS antigos).
- **Não mexer no Kanban nem no diário de bordo** dos projetos: a Bruna atualiza ela mesma (quando o Claude
  também atualizava, os cartões e as entradas ficavam duplicados). O Studyhub é o `Projeto` de **id 1**
  (o Time Tracking, outro projeto dela, é o id 2).
- **Dados pessoais nunca vão para o repositório público**: `db.sqlite3`, `backup/` e `dados/` estão no
  `.gitignore`; os dados viajam só pelo repositório privado (ver "Dados entre computadores"). Scripts que
  mexem nos dados dela (ex.: preencher cartões, marcar situações da grade) rodam via `manage.py shell` e
  não são commitados.

## Rodar em um computador novo (Windows)

```powershell
git clone https://github.com/Bmarques01/Studyhub.git
cd Studyhub
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser  # a conta para entrar (a Bruna digita a senha)
.\.venv\Scripts\python.exe manage.py receber_dados    # traz os dados do repositório privado
.\.venv\Scripts\python.exe manage.py runserver
```

Abrir http://127.0.0.1:8000.

## Conta (login)

- Todas as páginas exigem login: `LoginRequiredMiddleware` do Django em `config/settings.py`
  (`LOGIN_URL = 'entrar'`). Telas do próprio Django: `/entrar/`, `/sair/` (só POST, botão no menu),
  `/conta/senha/` (`config/contas.py`); templates em `templates/registration/`.
- **Sem cadastro pelo site**, de propósito (é para ir para a internet). A conta é criada com
  `manage.py createsuperuser` em cada computador: as contas **não** vão no `enviar_dados` (o app `auth`
  fica fora de `APPS`).
- A sessão dura 60 dias e se renova a cada página (`SESSION_SAVE_EVERY_REQUEST`), para não cair no meio
  de um pomodoro.
- Testes: os apps importam `TestCase` de `config/testes.py`, cujo cliente entra numa conta de teste
  sozinho. Teste novo → usar esse `TestCase` (o `config/tests.py` usa o do Django para testar o login).

## Dados entre computadores (sincronização)

O código fica no repositório **público** `Studyhub`; os **dados** ficam no repositório **privado**
`Bmarques01/Studyhub-dados` (config `DADOS_REPO` em `config/settings.py`, clonado em `dados/`, que está
no `.gitignore`). Lógica em `dashboard/sincronizacao.py`:

- `manage.py enviar_dados` — ao terminar de estudar: exporta o banco para `dados/studyhub.json`
  (dumpdata dos apps), commit e push. Recusa se o GitHub tiver dados mais novos que este computador ainda
  não recebeu (`--forcar` passa por cima).
- `manage.py receber_dados` — ao sentar em outro computador: puxa e substitui o banco local. Recusa se
  houver mudanças locais não enviadas, ou se for um computador novo que já tem dados (`--forcar`).
- A versão que cada computador conhece fica em `dados/.git/studyhub-ultima-versao`.
- O pomodoro em andamento fica no `localStorage` do navegador e não é sincronizado.
- `manage.py fazer_backup` continua existindo para um backup avulso em `backup/`.
- Ids são preservados (o Studyhub continua sendo o projeto 1).
- A lista de apps exportados é `APPS` em `dashboard/sincronizacao.py` (o `fazer_backup` usa a mesma).
  **App novo com dados → entra nessa lista.** Antes de usar o outro computador depois de uma mudança
  de código: `git pull`, `pip install -r requirements.txt`, `migrate` e só então `receber_dados`
  (um computador com código antigo enviaria um JSON sem as tabelas novas e apagaria esses dados).
- **Nunca** colocar dados pessoais no repositório público (inclui o Time Tracking, que tem dados da empresa).

## Comandos

- Testes: `.\.venv\Scripts\python.exe manage.py test` (todos devem passar antes de cada commit)
- Conferir migrações: `manage.py makemigrations --check --dry-run`
- No Git Bash: `.venv/Scripts/python.exe manage.py ...`

## Estrutura (apps Django)

| App | O que faz |
|---|---|
| `dashboard` | Página inicial: horas hoje/semana/mês, meta semanal (`Perfil`), sequência, gráfico, calendário, próximos eventos, tempo por disciplina/projeto, resumo dos projetos ativos (progresso, fazendo, feito no período, tempo, último diário), constância (quadrados dos dias do período + resumo). **Filtro de período** (`periodos.py`: esta semana / semana passada / este mês / mês passado, guardado na sessão) muda gráfico (período × anterior), calendário, disciplinas, constância e projetos; cards do topo, meta e próximos ficam fixos. Filtro `horas` em `templatetags/tempo.py`. Comandos `fazer_backup`, `enviar_dados`, `receber_dados`. |
| `pomodoro` | `SessaoPomodoro` (minutos + disciplina/tópico **ou** projeto/funcionalidade). Página do relógio e endpoint `registrar/` (JSON). |
| `estudos` | `Categoria` (tipo: graduação → semestres letivos "2026/2", pós → módulos, outro → sem divisão) → `Periodo` → `Disciplina` (cor, notas GA/GB) → `Topico`. Página de cada disciplina com estatísticas e notas. Modo leitura + lápis por categoria para editar. |
| `calendario` | `Evento` (prova, trabalho, entrega, outro), visão do mês e "próximos". |
| `curso` | `Grade` + `DisciplinaGrade` (situação, pré-requisitos, nota final). % concluído por carga horária, mapa da grade, liberadas/travadas. Grade de CC da Unisinos em `grade_cc_unisinos.py`, comando `importar_grade`. |
| `projetos` | `Projeto` (tipo pessoal/trabalho, data de início e fim) → `Funcionalidade` (Kanban: backlog/a_fazer/fazendo/feito; tipo; prioridade; estimativa) → `Tarefa` (checklist); `EntradaDiario` (devlog). Arrastar e soltar salva coluna e ordem. |
| `cadernos` | `Caderno` (capa, papel, fonte, cores; disciplina opcional) → `Pagina` (conteúdo em **Quill Delta JSON**, nunca HTML; salvamento automático). Página tem `tipo`: **escrita** ou **material** (guia pronto em HTML, ex.: feito pelo Claude, colado ou enviado como arquivo). O material roda num `iframe` com `sandbox="allow-scripts"` (sem `allow-same-origin`) servido por `paginas/<id>/material/` com CSP `sandbox` (isolado mesmo se aberto direto); o editor vira o bloco de anotações. Uma "ponte" injetada no `<head>` troca o `localStorage` (bloqueado no sandbox) por um que avisa o Studyhub via `postMessage` → salvo em `Pagina.armazenamento` (ex.: aulas marcadas como estudadas). |
| `flashcards` | `Flashcard` (disciplina obrigatória, tópico opcional, frente/verso + memória do FSRS) → `Revisao` (nota 1–4, duração). `memoria.py` faz a ponte com a biblioteca `fsrs` (sem fuzzing, para o intervalo do botão ser o real) e monta a fila: vencidos primeiro, depois novos até `Perfil.flashcards_novos_por_dia` (20). `importacao.py` lê o texto colado (`F:` / `V:`). Tela inicial = uma caixa por disciplina (agrupadas por categoria · período; aparecem as do período atual, mesmo vazias, e as antigas só se tiverem cartões) → página da disciplina (`disciplina/<id>/`) com um bloco por **baralho**, que é o próprio `Topico` da disciplina (criar baralho = criar tópico). Janela "+ novo" (`_novo.html`): cartão / colar vários / baralho. Revisão de tudo, de uma disciplina ou de um baralho (`?topico=`), por JSON (`revisar/proximo/`, `<id>/responder/`) com atalhos espaço e 1–4. Tempo de revisão só conta se a Bruna ligar um pomodoro. |

| `questoes` | `Questao` (disciplina obrigatória, tópico opcional; tipo **múltipla** → `Alternativa` com `correta`, **vf** → `resposta` "V"/"F", **aberta** → `resposta` esperada e a Bruna diz se acertou) → `Questionario` (ids sorteados em JSON, na ordem; `topicos` M2M + `sem_topico`: marcar vários tópicos, nenhum = disciplina inteira; botão "praticar" em cada bloco de tópico) → `Resposta` (acertou, resposta dada). Escrever no formulário (`nova/`, "salvar e escrever outra") ou **importar** colando/enviando `.txt` no formato `P:` / `A) ... *` / `R:` / `E:` (`importacao.py`, prévia antes de salvar, com o "pedido pronto" para o Claude). Questionário server-side em 3 momentos na mesma página (pergunta → correção `?ver=` → resultado), só aceita a resposta da questão da vez; atalhos A–H, V/F, S/N, Enter. "Refazer as erradas" cria um questionário novo. Usa as caixas do `flashcards.css`. "+ disciplina" (janela) cria a disciplina pela mesma função das Estudos (`salvar_nova_disciplina`) e já abre a página dela. **Caderno de erros** (`erros.py`, `/questoes/erros/`, item "Erros" do menu): `Erro` (1 por questão: motivo, anotação, última resposta errada, `vezes`, `origem` — vazia = questionário —, `dominado_em`). `registrar_erro` é chamado no `responder` quando ela erra (errar de novo uma dominada a devolve para a lista); a migração 0003 trouxe as respostas erradas antigas. Na correção: "por que errou?" (teclas 1–4) + anotação; acertou uma que estava nos erros → oferece "dominei". Página: filtro por disciplina, tópicos mais errados (barras) e motivos, "revisar" (questionário com `de_erros=True`, por disciplina ou tópico), dominados à parte. "+ erro" (questão de prova/lista de fora) vira questão **aberta** no banco + `Erro` com origem. Os nomes das URLs do caderno contêm "erro" (o menu usa isso para marcar "Erros"). |
| `ia` | **Gerar questões e flashcards com o Claude** (`/ia/gerar/`, botão "✦ gerar com IA" nas Questões e nos Flashcards, com `?disciplina=&topico=&so=questoes|flashcards`). Material: PDF dos slides (vai inteiro como `document` base64, máx. 20 MB), `.txt`/`.md` ou texto colado — **não é guardado**. `gerador.py`: Opus 5.5 (`claude-opus-5-5`, effort medium, streaming, `fallbacks="default"` com beta `server-side-fallback-2026-07-01`), resposta em JSON com esquema (`output_config.format`), convertida para o **texto da importação** (`P:`/`A)`/`R:`/`E:` e `F:`/`V:`; campos numa linha só e "· " na frente do que pareceria marcador). `Geracao` guarda o texto até a revisão, tokens, `custo` (tabela `PRECOS`, US$/milhão) e `erro` (resposta cortada/recusada: guarda o custo também). Revisão (`gerar/<id>/`): texto editável + prévia (`questoes/_previa.html`), "atualizar prévia" e salvar uma vez só por tipo. Custo do mês + últimas gerações na tela de pedir. Chave em `.env` (`ANTHROPIC_API_KEY`, lido com `python-dotenv`; modelo em `.env.exemplo`). Testes trocam `ia.gerador.pedir_ao_claude` por uma resposta falsa (não gastam créditos). |

Compartilhado: `templates/base.html` (menu lateral, mensagens, mini pomodoro), `templates/componentes/icone.html`
(ícones SVG por nome), `static/css/base.css` (paleta e componentes), `static/js/editar.js` (edição inline
`.editavel` / `.modo-ver` / `.modo-edicao`), `static/js/pomodoro-motor.js` e `pomodoro-mini.js`.

## Pomodoro (a parte mais delicada)

- **Motor** (`static/js/pomodoro-motor.js`) roda em **todas as páginas** e guarda o estado em
  `localStorage` (`pomodoro-estado`, `pomodoro-tempos`, `pomodoro-escolha`). O tempo é calculado pelo
  relógio (`Date.now()`), não por contagem — por isso continua ao trocar de página ou fechar a aba.
- Telas só **escutam** o motor (`Pomodoro.ouvir`): a página do pomodoro e o **mini pomodoro** no canto das
  outras páginas.
- Regras combinadas com a Bruna:
  - Só **foco e pausa** (sem pausa longa) + **meta de ciclos** ("ciclo 2 de 4").
  - **Automático**: ao fim do foco toca o sininho (3x) e a pausa começa sozinha; ao fim da pausa, o foco.
    Para quando a meta de ciclos é batida.
  - **"Ainda no foco?"** 1 min antes do fim: +5, +15, seguir sem limite (conta "+mm:ss") ou fazer a pausa.
  - **Encerrar** antes do tempo: salva os minutos feitos (≥ 1), conta como ciclo e para (não emenda pausa).
  - Em segundo plano o navegador só confere o relógio ~1x/min: o próximo bloco começa **a partir do fim
    previsto** do anterior. Só espera a Bruna ("pronta pra começar") se a pausa inteira já tiver passado.
  - Várias abas não registram a mesma sessão (`blocoId`). Som só toca depois de um clique na página
    (limitação do navegador); por isso também há notificação do sistema.
  - Som entre abas: só a aba que percebe o fim do bloco toca. Se ela não pode (sem clique), grava
    `somPendente` no estado e qualquer aba liberada toca no próximo `tick` (vale 2 min). O mini mostra
    "🔇 som bloqueado · clique para ativar" quando a página ainda não tem permissão de som.
  - **Ruído** (branco / rosa / marrom + volume, em `pomodoro-ruido`): gerado no motor (buffer de 8 s em
    loop, sem arquivo de áudio), toca **só com o foco rodando**. Controles na página do pomodoro e botão
    no mini. Ao trocar de página o navegador corta o som: volta no primeiro clique (o mini avisa "ruído
    parado"). Com várias abas, só a "dona" toca (`pomodoro-ruido-aba`, renovada a cada segundo).

## Visual (decidido com a Bruna)

- Rosa com pegada tech: variáveis no topo de `static/css/base.css` (`--rosa-forte #e0609a`, `--lilas #a77bf3`,
  `--degrade`...), fundo quadriculado rosa, fontes **Space Grotesk** (texto) e **JetBrains Mono** (logo,
  números, rótulos `// assim`). Logo `> studyhub_` com cursor piscando.
- Sem emojis no menu e na saudação do dashboard. Menu lateral; "em breve" para o que ainda não existe.
- **Cores de gráficos e estados são validadas** para daltonismo (script `validate_palette.js` da skill
  dataviz). Paletas em uso: semana atual `#e0609a` × passada `#8f6fd8`; mapa de calor
  `#f093bb, #e0609a, #bf3f7c, #8c2a5c`; eventos prova `#d64f8f`, trabalho `#6250d6`, entrega `#c98500`,
  outro = bolinha vazada; grade concluída `#c2417f`, compensada `#ee8fb7`, cursando `#5b4bd0`.
  Estados sempre com ícone/texto além da cor.

## Convenções de código

- Nomes de variáveis, funções, models e URLs **em português**. Comentários curtos e didáticos (a Bruna lê
  o código para aprender).
- Texto que vem do usuário vai para a página com `textContent` (JS) ou autoescape (templates); dados para
  o JS via `json_script`. POST com CSRF; redirecionamentos com `url_has_allowed_host_and_scheme`.
- Números em atributos/CSS: `floatformat:'1u'` e `|unlocalize` (o site está em pt-br, que usa vírgula).
- Cada funcionalidade nova vem com testes em `tests.py` do app.

## Armadilhas já encontradas

- Em consultas com `annotate(Count/Sum)`, o Django **ignora o `Meta.ordering`**: usar `order_by` explícito.
- `{% firstof ... as x %}` guarda **texto**, não o objeto: usar `{% with x=a|default:b %}`.
- Scripts de página que usam o motor do pomodoro precisam de `defer` (o motor também é `defer`).
- No Git Bash do Windows, heredocs longos com aspas às vezes quebram: escrever o script num arquivo
  temporário e rodar com `python arquivo.py`. `Set-Content` do PowerShell grava com BOM.

## Como testar no navegador (para mudanças de interface)

Os testes de Django não pegam erros de JavaScript. O que funcionou bem: um banco de **demonstração**
separado (settings que importa `config.settings` e troca `DATABASES`), `runserver 8001 --noreload`
(reiniciar após mudar templates), Edge headless com `--remote-debugging-port` e um script Node que fala o
DevTools Protocol pelo `WebSocket` nativo: clicar, digitar (`Input.insertText`), trocar `Date.now` para
"adiantar o relógio" do pomodoro e tirar prints (`Page.captureScreenshot`). Desligar o cache
(`Network.setCacheDisabled`) para não ver CSS antigo. Nunca testar no banco real da Bruna.

## Próximos passos

1. **IA (continuação)**: resumo de slides (PDF) direto no caderno; no caderno de erros, um botão "virar
   flashcard". Reaproveitar `ia/gerador.py` (e ler a skill `claude-api` antes).
2. **Deploy na AWS** (combinado: o Time Tracking — projeto id 2 — fica **só no computador**, não vai para
   a nuvem). Falta: configurações de produção (SECRET_KEY/DEBUG/ALLOWED_HOSTS por variável de ambiente,
   HTTPS), gunicorn (com `--timeout` alto: a geração com IA pode levar ~2 min), arquivos estáticos, backup do
   banco no S3, limite de tentativas de login, `ANTHROPIC_API_KEY` como variável de ambiente no servidor.
3. **Planejador de semestres** (pré-requisitos + previsão de formatura) e **atividades complementares**
   (100h, com limite por modalidade) no app `curso`.
4. Projetos: versões/changelog e integração com o GitHub.
