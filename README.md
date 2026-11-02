# > studyhub_

Plataforma pessoal de estudos, feita com Django. Junta num só lugar as ferramentas que eu uso para estudar.

## O que já tem

- **Dashboard**: horas de estudo no dia, na semana e no mês, meta semanal, sequência de dias, gráfico da semana, calendário do mês, próximos eventos, mapa de constância e tempo por disciplina
- **Pomodoro**: tempos e número de ciclos configuráveis, com cada sessão ligada a uma disciplina e a um tópico
- **Estudos**: categorias por tipo (graduação em semestres, pós em módulos, projetos) → Disciplina → Tópico, com cor por disciplina
- **Calendário**: provas, trabalhos e entregas no mês, com lista de próximos e marcação de feito
- **Curso**: grade curricular com % concluído (por carga horária), projeção do semestre, progresso por bloco, mapa da grade clicável, pré-requisitos (o que está liberado e o que está travado) e média geral
- **Projetos**: quadro Kanban com arrastar e soltar (backlog, a fazer, fazendo, feito), funcionalidades com tipo, prioridade, checklist e estimativa, tempo por funcionalidade pelo pomodoro e diário de bordo
- **Disciplina**: página própria com horas estudadas, gráfico semanal, tempo por tópico, notas GA/GB com cálculo do que falta, provas e entregas

## Próximos passos

- Versões/changelog e integração com o GitHub nos projetos
- Cadernos digitais com resumos gerados por IA a partir de slides
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

Para rodar os testes:

```bash
python manage.py test
```
