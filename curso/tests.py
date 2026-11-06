import io
from decimal import Decimal

from django.core.management import call_command
from config.testes import TestCase
from django.urls import reverse
from django.utils import timezone

from estudos.models import Categoria, Disciplina, semestre_letivo

from .models import DisciplinaGrade, Grade
from .views import contar_horas


def g(codigo):
    return DisciplinaGrade.objects.get(codigo=codigo)


class ImportacaoTests(TestCase):
    def test_importa_e_pode_rodar_de_novo(self):
        call_command('importar_grade', stdout=io.StringIO())
        call_command('importar_grade', stdout=io.StringIO())
        self.assertEqual(Grade.objects.count(), 1)
        obrigatorias = DisciplinaGrade.objects.filter(bloco='obrigatoria')
        self.assertEqual(obrigatorias.count(), 40)
        self.assertEqual(sum(d.carga_horaria for d in obrigatorias), 2880)
        self.assertEqual(list(g('061967').pre_requisitos.values_list('codigo', flat=True)), ['061950'])


class GradeTests(TestCase):
    def setUp(self):
        self.cc = Categoria.objects.create(nome='Ciência da Computação', tipo='graduacao')
        call_command('importar_grade', categoria=self.cc.id, stdout=io.StringIO())

    def marcar(self, situacao, *codigos):
        DisciplinaGrade.objects.filter(codigo__in=codigos).update(situacao=situacao)

    def test_contar_horas_respeita_o_exigido(self):
        class D:
            def __init__(self, s, h): self.situacao, self.carga_horaria = s, h
        partes = contar_horas([D('concluida', 80), D('concluida', 80), D('cursando', 80)], 160)
        self.assertEqual((partes['concluida'], partes['cursando'], partes['falta']), (160, 0, 0))

    def test_liberada_e_travada(self):
        self.assertTrue(g('061921').liberada)        # Cálculo Diferencial: sem pré-requisito
        self.assertFalse(g('061932').liberada)       # Cálculo Integral: falta Cálculo Diferencial
        self.marcar('concluida', '061921')
        self.assertTrue(g('061932').liberada)
        self.marcar('cursando', '061932')
        self.assertFalse(g('061932').liberada)       # já está cursando

    def test_compensada_conta_como_pre_requisito(self):
        self.marcar('compensada', '062123')
        self.assertTrue(g('061939').liberada)

    def test_progresso_na_pagina(self):
        self.marcar('concluida', '062123', '062136')    # 160h
        self.marcar('compensada', '001010')             # 40h
        self.marcar('cursando', '061949')               # 80h
        resposta = self.client.get(reverse('curso:index'))
        total = resposta.context['total']
        self.assertEqual((total['concluida'], total['compensada'], total['cursando']), (160, 40, 80))
        self.assertEqual(total['exigido'], 3200)
        self.assertAlmostEqual(total['pct_feito'], 200 / 3200 * 100)
        self.assertContains(resposta, 'mapa da grade')

    def test_marcar_cursando_cria_disciplina_em_estudos(self):
        apa = g('061949')
        self.client.post(reverse('curso:situacao', args=[apa.id]), {'situacao': 'cursando'})
        apa.refresh_from_db()
        self.assertEqual(apa.disciplina.nome, 'Análise e Projeto de Algoritmos')
        self.assertEqual(apa.disciplina.categoria, self.cc)
        self.assertEqual(apa.disciplina.periodo.nome, semestre_letivo(timezone.localdate()))
        self.assertEqual(apa.semestre_cursado, semestre_letivo(timezone.localdate()))
        # marcar de novo não cria outra
        self.client.post(reverse('curso:situacao', args=[apa.id]), {'situacao': 'cursando'})
        self.assertEqual(Disciplina.objects.filter(nome='Análise e Projeto de Algoritmos').count(), 1)

    def test_concluir_aproveita_grau_final_de_estudos(self):
        apa = g('061949')
        self.client.post(reverse('curso:situacao', args=[apa.id]), {'situacao': 'cursando'})
        apa.refresh_from_db()
        apa.disciplina.nota_ga, apa.disciplina.nota_gb = Decimal('7'), Decimal('6')
        apa.disciplina.save()

        pagina = self.client.get(reverse('estudos:disciplina', args=[apa.disciplina.id]))
        self.assertContains(pagina, 'marcar como concluída')

        self.client.post(reverse('curso:situacao', args=[apa.id]),
                         {'situacao': 'concluida', 'semestre_cursado': '2026/2'})
        apa.refresh_from_db()
        self.assertEqual(apa.nota_final, Decimal('6.33'))

    def test_media_geral_ponderada(self):
        DisciplinaGrade.objects.filter(codigo='001010').update(situacao='concluida', nota_final=Decimal('10'))  # 40h
        DisciplinaGrade.objects.filter(codigo='062123').update(situacao='concluida', nota_final=Decimal('7'))   # 80h
        resposta = self.client.get(reverse('curso:index'))
        self.assertEqual(resposta.context['media'], Decimal('8'))  # (10×40 + 7×80) / 120

    def test_nota_invalida_nao_salva(self):
        apa = g('061949')
        self.client.post(reverse('curso:situacao', args=[apa.id]), {'situacao': 'concluida', 'nota_final': '12'})
        apa.refresh_from_db()
        self.assertEqual(apa.situacao, 'nao_cursada')


class SemGradeTests(TestCase):
    def test_pagina_sem_grade(self):
        resposta = self.client.get(reverse('curso:index'))
        self.assertContains(resposta, 'importar_grade')
