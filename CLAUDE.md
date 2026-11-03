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
- **Manter o projeto "Studyhub" do próprio site atualizado** (pedido dela): ao começar uma tarefa, criar ou
  mover o cartão no Kanban para "fazendo"; ao terminar, para "feito", marcar as tarefas e anotar no diário
  de bordo (fiz / aprendi / travei). Fazer pelo `manage.py shell` no banco real. O Studyhub é o `Projeto`
  de **id 1** (o Time Tracking, outro projeto dela, é o id 2).
- **Dados pessoais nunca vão para o GitHub**: `db.sqlite3` e `backup/` estão no `.gitignore`. Scripts que
  mexem nos dados dela (ex.: preencher cartões, marcar situações da grade) rodam via `manage.py shell` e
  não são commitados.

## Rodar em um computador novo (Windows)

```powershell
git clone https://github.com/Bmarques01/Studyhub.git
cd Studyhub
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
# trazer os dados: copiar o arquivo de backup para a pasta backup\ e carregar
.\.venv\Scripts\python.exe manage.py loaddata backup\studyhub-AAAA-MM-DD.json
.\.venv\Scripts\python.exe manage.py runserver
```

Abrir http://127.0.0.1:8000. Sem o backup, o site abre vazio (e a grade do curso pode ser recriada com
`manage.py importar_grade --categoria ID`, mas sem as situações marcadas).

**Backup dos dados:** `python manage.py fazer_backup` gera `backup/studyhub-AAAA-MM-DD.json` com tudo
(estudos, pomodoros, calendário, curso, projetos, cadernos). Para levar a outro computador, copiar esse
arquivo à parte (OneDrive, pendrive...) e rodar `loaddata` como acima, **depois** do `migrate` e com o
banco ainda vazio. Os ids são preservados (o Studyhub continua sendo o projeto 1).

## Comandos

- Testes: `.\.venv\Scripts\python.exe manage.py test` (todos devem passar antes de cada commit)
- Conferir migrações: `manage.py makemigrations --check --dry-run`
- No Git Bash: `.venv/Scripts/python.exe manage.py ...`

## Estrutura (apps Django)

| App | O que faz |
|---|---|
| `dashboard` | Página inicial: horas hoje/semana/mês, meta semanal (`Perfil`), sequência, gráfico da semana, calendário do mês, próximos eventos, tempo por disciplina/projeto, mapa de constância (40 semanas). Filtro `horas` em `templatetags/tempo.py`. Comando `fazer_backup`. |
| `pomodoro` | `SessaoPomodoro` (minutos + disciplina/tópico **ou** projeto/funcionalidade). Página do relógio e endpoint `registrar/` (JSON). |
| `estudos` | `Categoria` (tipo: graduação → semestres letivos "2026/2", pós → módulos, outro → sem divisão) → `Periodo` → `Disciplina` (cor, notas GA/GB) → `Topico`. Página de cada disciplina com estatísticas e notas. Modo leitura + lápis por categoria para editar. |
| `calendario` | `Evento` (prova, trabalho, entrega, outro), visão do mês e "próximos". |
| `curso` | `Grade` + `DisciplinaGrade` (situação, pré-requisitos, nota final). % concluído por carga horária, mapa da grade, liberadas/travadas. Grade de CC da Unisinos em `grade_cc_unisinos.py`, comando `importar_grade`. |
| `projetos` | `Projeto` → `Funcionalidade` (Kanban: backlog/a_fazer/fazendo/feito; tipo; prioridade; estimativa) → `Tarefa` (checklist); `EntradaDiario` (devlog). Arrastar e soltar salva coluna e ordem. |
| `cadernos` | `Caderno` (capa, papel, fonte, cores; disciplina opcional) → `Pagina` (conteúdo em **Quill Delta JSON**, nunca HTML; salvamento automático). |

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

1. **Questionário + caderno de erros** (proposta feita, aguardando respostas da Bruna):
   banco de questões por disciplina/tópico (múltipla escolha, V/F, aberta) com explicação; **importar em
   bulk** colando texto no formato abaixo (a Bruna pede ao Claude para gerar questões e cola); questionário
   com correção na hora; todo erro entra sozinho no **caderno de erros** com "por que errei" (não sabia,
   confundi conceitos, falta de atenção, interpretei errado) e anotação; revisão só dos erros, "dominado"
   após acertar 2x seguidas; erros manuais de provas/listas; atalho "Erros" na página da disciplina com os
   tópicos mais errados. Perguntas em aberto: os 3 tipos de questão? 2 ou 3 acertos para dominar? Erros
   manuais?
   ```
   P: Qual protocolo de transporte o BGP usa?
   A) UDP
   B) TCP *
   C) ICMP
   E: O BGP usa TCP na porta 179 para ter entrega confiável.

   P: [V/F] O BGP é um protocolo de roteamento interno (IGP).
   R: F
   E: O BGP é um EGP, usado entre sistemas autônomos.
   ```
2. **IA**: resumo de slides (PDF) direto no caderno e geração de questões no formato acima. Precisa de
   chave da API da Anthropic (a Bruna ainda vai criar). Antes de escrever o código, ler a skill
   `claude-api`.
3. **Flashcards** com repetição espaçada (FSRS), podendo nascer dos erros.
4. **Planejador de semestres** (pré-requisitos + previsão de formatura) e **atividades complementares**
   (100h, com limite por modalidade) no app `curso`.
5. Projetos: versões/changelog e integração com o GitHub.
