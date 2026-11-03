"""Repetição espaçada: a ponte entre os nossos cartões e a biblioteca fsrs.

O FSRS estima quanto tempo você ainda lembra de cada cartão e marca a próxima revisão
para pouco antes de você esquecer. Aqui ficam:
- responder(): aplica a nota (de novo / difícil / bom / fácil) e salva a nova data;
- intervalos(): quanto tempo cada botão daria (o "3 dias" embaixo do botão);
- a fila do dia: o que vence agora + cartões novos, respeitando o limite diário.
"""
from datetime import timedelta

import fsrs
from django.db.models import Count, Q
from django.utils import timezone

from dashboard.models import Perfil

from .models import Flashcard, Revisao

# Sem "fuzzing" (um sorteio de alguns dias para mais ou para menos): assim o intervalo
# mostrado no botão é exatamente o que acontece quando você clica.
AGENDADOR = fsrs.Scheduler(desired_retention=0.9, enable_fuzzing=False)

# Se só sobraram cartões "em aprendizagem" que vencem logo, eles aparecem antes da hora
# (em vez de você esperar 8 minutos olhando para a tela).
ANTECIPAR = timedelta(minutes=20)


# ===== Uma resposta =====

def para_fsrs(cartao, agora):
    """Converte o nosso cartão para o formato da biblioteca."""
    return fsrs.Card(
        card_id=cartao.pk,
        state=fsrs.State(cartao.estado),
        step=cartao.passo,
        stability=cartao.estabilidade,
        difficulty=cartao.dificuldade,
        due=cartao.vencimento or agora,
        last_review=cartao.ultima_revisao,
    )


def simular(cartao, nota, agora):
    """Como o cartão ficaria com essa nota (sem salvar nada)."""
    resultado, _ = AGENDADOR.review_card(para_fsrs(cartao, agora), fsrs.Rating(nota), agora)
    return resultado


def responder(cartao, nota, agora=None, duracao_segundos=None):
    agora = agora or timezone.now()
    resultado = simular(cartao, nota, agora)
    cartao.estado = resultado.state.value
    cartao.passo = resultado.step
    cartao.estabilidade = resultado.stability
    cartao.dificuldade = resultado.difficulty
    cartao.vencimento = resultado.due
    cartao.ultima_revisao = agora
    if cartao.primeira_revisao is None:
        cartao.primeira_revisao = agora
    cartao.save()
    Revisao.objects.create(flashcard=cartao, nota=nota, revisada_em=agora,
                           duracao_segundos=duracao_segundos)
    return cartao


def texto_intervalo(tempo):
    """timedelta → texto curto: '<1 min', '10 min', '5 h', '3 dias', '2 meses', '1,5 anos'."""
    segundos = tempo.total_seconds()
    if segundos < 60:
        return '<1 min'
    if segundos < 3600:
        return f'{round(segundos / 60)} min'
    if segundos < 86400:
        return f'{round(segundos / 3600)} h'
    dias = round(segundos / 86400)
    if dias < 31:
        return f'{dias} dia{"s" if dias > 1 else ""}'
    if dias < 365:
        meses = round(dias / 30)
        return f'{meses} {"mês" if meses == 1 else "meses"}'
    anos = round(dias / 365, 1)
    return f'{anos:g} ano{"s" if anos >= 2 else ""}'.replace('.', ',')


def intervalos(cartao, agora=None):
    """{nota: texto} para os 4 botões da revisão."""
    agora = agora or timezone.now()
    return {nota: texto_intervalo(simular(cartao, nota, agora).due - agora) for nota in (1, 2, 3, 4)}


# ===== Fila do dia =====

def novos_feitos_hoje():
    """Quantos cartões novos você viu pela primeira vez hoje (contam para o limite diário)."""
    return Flashcard.objects.filter(primeira_revisao__date=timezone.localdate()).count()


def vagas_de_novos():
    return max(0, Perfil.atual().flashcards_novos_por_dia - novos_feitos_hoje())


def do_filtro(disciplina=None):
    cartoes = Flashcard.objects.all()
    return cartoes.filter(disciplina=disciplina) if disciplina else cartoes


def proximo_cartao(disciplina=None, agora=None):
    """Qual cartão mostrar agora: primeiro os vencidos, depois os novos (se ainda houver vaga hoje)."""
    agora = agora or timezone.now()
    cartoes = do_filtro(disciplina)
    vistos = cartoes.filter(primeira_revisao__isnull=False)

    cartao = vistos.filter(vencimento__lte=agora).order_by('vencimento', 'id').first()
    if not cartao and vagas_de_novos():
        cartao = cartoes.filter(primeira_revisao__isnull=True).order_by('criado_em', 'id').first()
    if not cartao:
        cartao = (vistos.filter(estado__in=[1, 3], vencimento__lte=agora + ANTECIPAR)
                  .order_by('vencimento', 'id').first())
    return cartao


def para_revisar(disciplina=None, agora=None):
    """Quantos cartões estão esperando agora (vencidos + novos dentro do limite)."""
    agora = agora or timezone.now()
    cartoes = do_filtro(disciplina)
    vencidos = cartoes.filter(primeira_revisao__isnull=False, vencimento__lte=agora).count()
    novos = cartoes.filter(primeira_revisao__isnull=True).count()
    return vencidos + min(novos, vagas_de_novos())


def resumo_por_disciplina(agora=None):
    """{disciplina_id: {'total', 'para_revisar'}} de todas as disciplinas que têm cartões."""
    agora = agora or timezone.now()
    vagas = vagas_de_novos()
    linhas = (Flashcard.objects.values('disciplina')
              .annotate(total=Count('id'),
                        vencidos=Count('id', filter=Q(primeira_revisao__isnull=False,
                                                      vencimento__lte=agora)),
                        novos=Count('id', filter=Q(primeira_revisao__isnull=True)))
              .order_by())
    return {
        linha['disciplina']: {'total': linha['total'],
                              'para_revisar': linha['vencidos'] + min(linha['novos'], vagas)}
        for linha in linhas
    }


def proxima_revisao(disciplina=None, agora=None):
    """Quando vence o próximo cartão (para a tela de "acabou por hoje"). None se não houver."""
    agora = agora or timezone.now()
    cartao = (do_filtro(disciplina).filter(primeira_revisao__isnull=False, vencimento__gt=agora)
              .order_by('vencimento').first())
    return cartao.vencimento if cartao else None
