from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from estudos.models import semestre_letivo

from .models import DisciplinaGrade, Grade

SEMESTRES = range(1, 9)


class SituacaoForm(forms.ModelForm):
    class Meta:
        model = DisciplinaGrade
        fields = ['situacao', 'semestre_cursado', 'nota_final']


# ===== Cálculos =====

def contar_horas(disciplinas, exigido):
    """Horas de um bloco por situação, sem passar do exigido.
    Ex.: optativas exigem 160h; se você fez 240h, contam só 160h.
    A ordem de preenchimento é: concluída → compensada → cursando → falta."""
    def soma(situacao):
        return sum(d.carga_horaria for d in disciplinas if d.situacao == situacao)

    restante = exigido
    partes = {}
    for situacao in ('concluida', 'compensada', 'cursando'):
        partes[situacao] = min(soma(situacao), restante)
        restante -= partes[situacao]
    partes['falta'] = restante
    partes['exigido'] = exigido
    partes['feito'] = partes['concluida'] + partes['compensada']
    return partes


def com_porcentagens(partes):
    """Acrescenta a largura (%) de cada pedaço da barra."""
    total = partes['exigido'] or 1
    for chave in ('concluida', 'compensada', 'cursando', 'falta'):
        partes[f'pct_{chave}'] = partes[chave] / total * 100
    partes['pct_feito'] = partes['feito'] / total * 100
    return partes


def progresso(grade, disciplinas):
    por_bloco = {b: [d for d in disciplinas if d.bloco == b] for b, _ in DisciplinaGrade.BLOCOS}
    blocos = [
        ('Obrigatórias', contar_horas(por_bloco['obrigatoria'],
                                      sum(d.carga_horaria for d in por_bloco['obrigatoria']))),
        ('Optativas', contar_horas(por_bloco['optativa'], grade.horas_optativas)),
        ('Transversais', contar_horas(por_bloco['transversal'], grade.horas_transversais)),
    ]
    total = {chave: sum(b[chave] for _, b in blocos)
             for chave in ('concluida', 'compensada', 'cursando', 'falta', 'exigido', 'feito')}
    total = com_porcentagens(total)
    total['pct_projecao'] = (total['feito'] + total['cursando']) / (total['exigido'] or 1) * 100
    return total, [(nome, com_porcentagens(partes)) for nome, partes in blocos]


def media_geral(disciplinas):
    """Média das notas finais, ponderada pela carga horária."""
    com_nota = [d for d in disciplinas if d.situacao == 'concluida' and d.nota_final is not None]
    horas = sum(d.carga_horaria for d in com_nota)
    if not horas:
        return None
    return sum(d.nota_final * d.carga_horaria for d in com_nota) / horas


# ===== Páginas =====

def index(request):
    grade = Grade.objects.select_related('categoria').first()
    if grade is None:
        return render(request, 'curso/sem_grade.html')

    disciplinas = list(grade.disciplinas.select_related('disciplina').prefetch_related('pre_requisitos', 'libera'))
    total, blocos = progresso(grade, disciplinas)
    obrigatorias = [d for d in disciplinas if d.bloco == 'obrigatoria']

    for d in disciplinas:
        d.pendentes = d.pre_requisitos_pendentes()

    # Liberadas: as que destravam mais disciplinas vêm primeiro (bom critério para a matrícula)
    liberadas = sorted([d for d in obrigatorias if d.liberada],
                       key=lambda d: (-len(d.libera.all()), d.semestre))
    travadas = [d for d in obrigatorias if d.situacao in ('nao_cursada', 'reprovada') and d.pendentes]

    mapa = [{
        'semestre': s,
        'disciplinas': [d for d in obrigatorias if d.semestre == s],
    } for s in SEMESTRES]
    for coluna in mapa:
        coluna['horas_feitas'] = sum(d.carga_horaria for d in coluna['disciplinas'] if d.feita)
        coluna['horas'] = sum(d.carga_horaria for d in coluna['disciplinas'])

    return render(request, 'curso/index.html', {
        'grade': grade,
        'total': total,
        'blocos': blocos,
        'media': media_geral(disciplinas),
        'mapa': mapa,
        'optativas': [d for d in disciplinas if d.bloco == 'optativa'],
        'transversais': [d for d in disciplinas if d.bloco == 'transversal'],
        'liberadas': liberadas,
        'travadas': travadas,
        'situacoes': DisciplinaGrade.SITUACOES,
        'letivo_atual': semestre_letivo(timezone.localdate()),
    })


@require_POST
def mudar_situacao(request, disciplina_id):
    item = get_object_or_404(DisciplinaGrade.objects.select_related('grade__categoria', 'disciplina'),
                             id=disciplina_id)
    form = SituacaoForm(request.POST, instance=item)
    if not form.is_valid():
        for erros in form.errors.values():
            for erro in erros:
                messages.error(request, erro)
    else:
        item = form.save()
        if item.situacao == 'cursando':
            if not item.semestre_cursado:
                item.semestre_cursado = semestre_letivo(timezone.localdate())
                item.save(update_fields=['semestre_cursado'])
            if item.ligar_aos_estudos():
                messages.success(request, f'"{item.nome}" está em Estudos, no semestre {item.disciplina.periodo}.')
        elif item.situacao == 'concluida' and item.nota_final is None and item.disciplina:
            # aproveita o Grau Final calculado em Estudos (GA e GB)
            if item.disciplina.grau_final is not None:
                item.nota_final = item.disciplina.grau_final
                item.save(update_fields=['nota_final'])

    destino = request.POST.get('proximo')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(reverse('curso:index') + f'#d{item.id}')
