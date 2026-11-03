# > studyhub_

Plataforma pessoal de estudos, feita com Django. Junta num só lugar as ferramentas que eu uso para estudar.

## O que já tem

- **Dashboard**: horas de estudo no dia, na semana e no mês, meta semanal, sequência de dias, gráfico da semana, calendário do mês, próximos eventos, mapa de constância e tempo por disciplina
- **Pomodoro**: tempos e número de ciclos configuráveis, com cada sessão ligada a uma disciplina e a um tópico
- **Estudos**: categorias por tipo (graduação em semestres, pós em módulos, projetos) → Disciplina → Tópico, com cor por disciplina
- **Calendário**: provas, trabalhos e entregas no mês, com lista de próximos e marcação de feito
- **Curso**: grade curricular com % concluído (por carga horária), projeção do semestre, progresso por bloco, mapa da grade clicável, pré-requisitos (o que está liberado e o que está travado) e média geral
- **Projetos**: quadro Kanban com arrastar e soltar (backlog, a fazer, fazendo, feito), funcionalidades com tipo, prioridade, checklist e estimativa, tempo por funcionalidade pelo pomodoro e diário de bordo
- **Cadernos**: cadernos digitais (de uma disciplina ou livres) com capa, papel (liso, pautado, quadriculado, pontilhado), fonte e cores próprias; editor com títulos, marca-texto, listas, checklist, código e links; salvamento automático
- **Disciplina**: página própria com horas estudadas, gráfico semanal, tempo por tópico, notas GA/GB com cálculo do que falta, provas e entregas

## Próximos passos

- Versões/changelog e integração com o GitHub nos projetos
- Resumos gerados por IA a partir de slides, direto nos cadernos
- Flashcards com repetição espaçada
- Caderno de erros

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py importar_grade --categoria ID   # opcional: grade de CC da Unisinos
python manage.py runserver
```

Depois é só abrir http://127.0.0.1:8000

## Usar em mais de um computador

O banco (`db.sqlite3`) não vai para este repositório, porque tem dados pessoais. Os dados viajam por um
**repositório privado** (configurado em `DADOS_REPO`, em `config/settings.py`):

```bash
python manage.py enviar_dados    # ao terminar de estudar: manda os dados para o repositório privado
python manage.py receber_dados   # ao sentar no outro computador: traz os dados mais novos
```

Os comandos avisam antes de sobrescrever algo que ainda não foi sincronizado.

Para rodar os testes:

```bash
python manage.py test
```
