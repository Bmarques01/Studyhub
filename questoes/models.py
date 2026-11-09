from django.db import models
from django.utils import timezone

from estudos.models import Disciplina, Topico


class Questao(models.Model):
    """Uma questão do banco. A resposta certa depende do tipo:
    múltipla escolha → a alternativa marcada como correta; V/F → "V" ou "F" em `resposta`;
    aberta → o texto esperado em `resposta` (você mesma confere se acertou)."""

    TIPOS = [
        ('multipla', 'múltipla escolha'),
        ('vf', 'verdadeiro ou falso'),
        ('aberta', 'aberta'),
    ]

    disciplina = models.ForeignKey(Disciplina, on_delete=models.CASCADE, related_name='questoes')
    topico = models.ForeignKey(Topico, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='questoes')
    tipo = models.CharField(max_length=10, choices=TIPOS, default='multipla')
    enunciado = models.TextField()
    resposta = models.TextField(blank=True)
    explicacao = models.TextField(blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criada_em', 'id']
        verbose_name = 'questão'
        verbose_name_plural = 'questões'

    def __str__(self):
        return self.enunciado[:60]

    def texto_da_resposta(self):
        """A resposta certa escrita por extenso, para mostrar depois de responder."""
        if self.tipo == 'vf':
            return 'Verdadeiro' if self.resposta == 'V' else 'Falso'
        if self.tipo == 'aberta':
            return self.resposta
        certa = next((a for a in self.alternativas.all() if a.correta), None)
        return f'{certa.letra}) {certa.texto}' if certa else ''


class Alternativa(models.Model):
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, related_name='alternativas')
    texto = models.TextField()
    correta = models.BooleanField(default=False)
    ordem = models.PositiveSmallIntegerField(default=0)  # 0 = A, 1 = B...

    class Meta:
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.letra}) {self.texto[:40]}'

    @property
    def letra(self):
        return chr(ord('A') + self.ordem)


class Questionario(models.Model):
    """Uma rodada de questões: quais caíram (na ordem) e as respostas dadas."""

    disciplina = models.ForeignKey(Disciplina, on_delete=models.CASCADE, related_name='questionarios')
    # Os tópicos escolhidos (nenhum = a disciplina inteira) e se entraram as questões sem tópico
    topicos = models.ManyToManyField(Topico, blank=True, related_name='questionarios')
    sem_topico = models.BooleanField(default=False)
    de_erros = models.BooleanField(default=False)  # revisão do caderno de erros
    questoes = models.JSONField(default=list)  # ids das questões, na ordem em que aparecem
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']

    def __str__(self):
        return f'{self.disciplina} · {timezone.localtime(self.criado_em):%d/%m %H:%M}'

    def nome_dos_topicos(self):
        """Ex.: "BGP, OSPF, sem tópico". Vazio = a disciplina inteira."""
        nomes = [t.nome for t in self.topicos.all()]
        if self.sem_topico:
            nomes.append('sem tópico')
        return ', '.join(nomes)


class Resposta(models.Model):
    """Cada resposta dada. Guarda o histórico (o caderno de erros vai partir daqui)."""

    questionario = models.ForeignKey(Questionario, on_delete=models.CASCADE, null=True, blank=True,
                                     related_name='respostas')
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, related_name='respostas')
    resposta_dada = models.TextField(blank=True)  # a letra, "V"/"F" ou o texto escrito
    acertou = models.BooleanField()
    respondida_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['respondida_em', 'id']

    def __str__(self):
        return f'{self.questao} · {"acertou" if self.acertou else "errou"}'


class Erro(models.Model):
    """Caderno de erros: uma questão que você errou e ainda não domina.
    Entra sozinha quando você erra no questionário (ou pelo "+ erro", para questões de fora).
    Só sai da lista quando você marca "dominei"; se errar de novo depois, volta."""

    MOTIVOS = [
        ('nao_sabia', 'não sabia'),
        ('confundi', 'confundi conceitos'),
        ('atencao', 'falta de atenção'),
        ('interpretei', 'interpretei errado'),
    ]

    questao = models.OneToOneField(Questao, on_delete=models.CASCADE, related_name='erro')
    motivo = models.CharField(max_length=12, choices=MOTIVOS, blank=True)  # vazio = ainda não disse
    anotacao = models.TextField(blank=True)
    resposta_dada = models.TextField(blank=True)  # a última resposta errada
    vezes = models.PositiveIntegerField(default=1)  # quantas vezes já errou
    origem = models.CharField(max_length=100, blank=True)  # vazio = questionário; ex.: "Prova GA"
    criado_em = models.DateTimeField(default=timezone.now)
    errou_em = models.DateTimeField(default=timezone.now)  # o erro mais recente
    dominado_em = models.DateTimeField(null=True, blank=True)  # None = ainda na lista

    class Meta:
        ordering = ['-errou_em', '-id']

    def __str__(self):
        return f'Erro · {self.questao}'

    def texto_da_resposta_dada(self):
        """A sua resposta por extenso. Ex.: "B) TCP", "Verdadeiro" ou o texto escrito."""
        q = self.questao
        if q.tipo == 'vf':
            return {'V': 'Verdadeiro', 'F': 'Falso'}.get(self.resposta_dada, self.resposta_dada)
        if q.tipo == 'multipla':
            marcada = next((a for a in q.alternativas.all() if a.letra == self.resposta_dada), None)
            return f'{marcada.letra}) {marcada.texto}' if marcada else self.resposta_dada
        return self.resposta_dada or '(respondida de cabeça)'


def registrar_erro(questao, resposta_dada, quando=None):
    """Põe a questão no caderno de erros. Se ela já estava lá, conta mais uma vez
    (e, se você tinha marcado "dominei", ela volta para a lista)."""
    quando = quando or timezone.now()
    erro, novo = Erro.objects.get_or_create(
        questao=questao, defaults={'resposta_dada': resposta_dada, 'criado_em': quando, 'errou_em': quando})
    if not novo:
        erro.vezes += 1
        erro.resposta_dada = resposta_dada
        erro.errou_em = quando
        erro.dominado_em = None
        erro.save()
    return erro


def desfazer_erro(resposta):
    """O contrário do registrar_erro, para o "cliquei errado": se a questão entrou no caderno
    só por causa desta resposta, ela sai; se já estava lá, conta uma vez a menos."""
    erro = Erro.objects.filter(questao_id=resposta.questao_id).first()
    if not erro:
        return
    if erro.vezes <= 1:
        erro.delete()
        return
    erro.vezes -= 1
    # a "última resposta errada" volta a ser a de antes desta
    anterior = (Resposta.objects.filter(questao_id=resposta.questao_id, acertou=False)
                .exclude(id=resposta.id).order_by('-respondida_em').first())
    if anterior:
        erro.resposta_dada = anterior.resposta_dada
        erro.errou_em = anterior.respondida_em
    erro.save()
