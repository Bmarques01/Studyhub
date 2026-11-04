// Página do pomodoro: mostra o relógio grande e as escolhas (disciplina, tópico, tempos).
// A contagem de tempo fica no motor (static/js/pomodoro-motor.js), que roda em todas as
// páginas: por isso o pomodoro continua quando você vai para outra parte do site.
const P = window.Pomodoro;

// ===== Elementos da página =====
const secao = document.querySelector('.pomodoro');
const card = document.querySelector('.relogio-card');
const elTempo = document.getElementById('tempo');
const elCiclo = document.getElementById('ciclo');
const elModo = document.getElementById('modo-atual');
const anel = document.getElementById('anel');
const campoTarefa = document.getElementById('tarefa');
const btnIniciar = document.getElementById('btn-iniciar');
const btnFinalizar = document.getElementById('btn-finalizar');
const aviso = document.getElementById('aviso-foco');
const barraLivre = document.getElementById('foco-livre');
const selDisciplina = document.getElementById('disciplina');
const selTopico = document.getElementById('topico');

// O que aparece na 2ª lista para cada escolha da 1ª, enviado pelo Django:
// { "3": [tópicos da disciplina 3], "p:5": [funcionalidades do projeto 5] }
const TOPICOS = JSON.parse(document.getElementById('dados-topicos').textContent);

// Comprimento da borda do círculo (2 × π × raio), usado para desenhar o progresso
const CIRCUNFERENCIA = 2 * Math.PI * 90;
anel.style.strokeDasharray = CIRCUNFERENCIA;

// ===== Desenhar a tela a partir do estado do motor =====
function atualizarTela() {
    const estado = P.estado;
    const texto = P.textoDoTempo();
    elTempo.textContent = texto;
    document.title = `${texto} · ${P.NOMES[estado.modo]}`;  // aparece na aba do navegador
    anel.style.strokeDashoffset = CIRCUNFERENCIA * (1 - P.fracaoRestante());
    elModo.textContent = P.NOMES[estado.modo].toLowerCase();
    elCiclo.textContent = P.textoDoCiclo();
    btnIniciar.textContent = estado.rodando ? 'Pausar' : (P.decorridoMs() > 0 ? 'Continuar' : 'Iniciar');

    card.classList.toggle('pausa', estado.modo !== 'foco');
    card.classList.toggle('livre', estado.livre);
    aviso.hidden = !P.mostrarAviso();
    barraLivre.hidden = !estado.livre;
    btnFinalizar.hidden = !(estado.rodando || estado.acumuladoMs > 0 || estado.livre);
}

// ===== Lista "hoje" =====
function adicionarNaLista(dados) {
    document.getElementById('total-minutos').textContent = dados.minutos_hoje;
    const lista = document.getElementById('lista-sessoes');
    lista.querySelector('.vazio')?.remove();

    // textContent (e não innerHTML) evita que texto digitado vire código na página
    const criar = (tag, classe, texto) => {
        const el = document.createElement(tag);
        if (classe) el.className = classe;
        el.textContent = texto;
        return el;
    };

    const item = document.createElement('li');
    if (dados.cor) item.style.setProperty('--cor', dados.cor);

    const nome = document.createElement('span');
    nome.className = 'nome';
    const titulo = (dados.disciplina || 'Foco') + (dados.topico ? ` · ${dados.topico}` : '');
    nome.appendChild(criar('strong', '', titulo));
    if (dados.tarefa) nome.appendChild(criar('small', '', dados.tarefa));

    item.append(criar('span', 'hora', dados.hora), nome, criar('span', 'min', `${dados.duracao_minutos} min`));
    lista.prepend(item);
}

P.ouvir((tipo, dados) => {
    if (tipo === 'sessao') adicionarNaLista(dados);
    atualizarTela();
});

// ===== Escolha de disciplina/projeto e tópico/funcionalidade =====
// Fica salva no navegador: o motor usa para registrar a sessão, em qualquer página.
function preencherTopicos() {
    const itens = TOPICOS[selDisciplina.value] || [];
    const vazio = selDisciplina.value.startsWith('p:') ? 'Sem funcionalidade' : 'Sem tópico';
    selTopico.replaceChildren(new Option(vazio, ''));
    itens.forEach(t => selTopico.add(new Option(t.nome, t.id)));
    selTopico.disabled = itens.length === 0;
}

function lembrarEscolha() {
    localStorage.setItem(P.CHAVE_ESCOLHA, JSON.stringify({
        disciplina: selDisciplina.value,
        topico: selTopico.value,
        tarefa: campoTarefa.value.trim(),
    }));
}

selDisciplina.addEventListener('change', () => { preencherTopicos(); lembrarEscolha(); });
selTopico.addEventListener('change', lembrarEscolha);
campoTarefa.addEventListener('input', lembrarEscolha);

// Ao abrir a página: se veio de "estudar agora"/"trabalhar nisso", usa essa escolha;
// senão, volta para a última escolha (se ainda existir)
const escolhaSalva = JSON.parse(localStorage.getItem(P.CHAVE_ESCOLHA) || '{}');
if (secao.dataset.disciplinaInicial) {
    selDisciplina.value = secao.dataset.disciplinaInicial;
    preencherTopicos();
    if (secao.dataset.segundaInicial) selTopico.value = secao.dataset.segundaInicial;
} else if (escolhaSalva.disciplina && TOPICOS[escolhaSalva.disciplina]) {
    selDisciplina.value = escolhaSalva.disciplina;
    preencherTopicos();
    if (TOPICOS[escolhaSalva.disciplina].some(t => String(t.id) === escolhaSalva.topico)) {
        selTopico.value = escolhaSalva.topico;
    }
}
campoTarefa.value = escolhaSalva.tarefa || '';
lembrarEscolha();

// ===== Botões e teclado =====
btnIniciar.addEventListener('click', P.alternar);
document.getElementById('btn-reiniciar').addEventListener('click', P.recomecar);
document.getElementById('btn-pular').addEventListener('click', P.pular);  // não conta como concluído
document.getElementById('btn-livre').addEventListener('click', P.seguirSemLimite);
document.getElementById('btn-fazer-pausa').addEventListener('click', P.fecharAviso);
document.getElementById('btn-encerrar').addEventListener('click', P.encerrar);
btnFinalizar.addEventListener('click', () => {
    if (confirm(P.textoParaEncerrar())) P.finalizar();
});
document.querySelectorAll('[data-estender]').forEach(botao => {
    botao.addEventListener('click', () => P.estender(Number(botao.dataset.estender)));
});

document.addEventListener('keydown', evento => {
    const digitando = ['INPUT', 'SELECT'].includes(evento.target.tagName);
    if (evento.code === 'Space' && !digitando) {
        evento.preventDefault();
        P.alternar();
    }
});

// ===== Ruído (branco, rosa, marrom) =====
// O som em si fica no motor: aqui só mostramos o estado e mandamos as mudanças.
const btnRuido = document.getElementById('ruido-ligar');
const volumeRuido = document.getElementById('ruido-volume');
const estadoRuido = document.getElementById('ruido-estado');
const botoesTipo = document.querySelectorAll('[data-ruido-tipo]');

function desenharRuido() {
    const ruido = P.ruido;
    btnRuido.setAttribute('aria-pressed', ruido.ligado);
    btnRuido.title = ruido.ligado ? 'Desligar o ruído' : 'Ligar o ruído (toca só durante o foco)';
    botoesTipo.forEach(botao => botao.classList.toggle('escolhido', botao.dataset.ruidoTipo === ruido.tipo));
    if (document.activeElement !== volumeRuido) volumeRuido.value = ruido.volume;
    let texto = 'desligado';
    if (ruido.ligado && P.ruidoNoFoco()) texto = P.somLiberado() ? 'tocando' : 'clique na página para tocar';
    else if (ruido.ligado) texto = 'toca durante o foco';
    estadoRuido.textContent = texto;
}

btnRuido.addEventListener('click', () => P.definirRuido({ ligado: !P.ruido.ligado }));
// escolher um tipo já liga o ruído
botoesTipo.forEach(botao => botao.addEventListener('click', () => P.definirRuido({ tipo: botao.dataset.ruidoTipo, ligado: true })));
volumeRuido.addEventListener('input', () => P.definirRuido({ volume: Number(volumeRuido.value) }));
P.ouvir(tipo => { if (tipo !== 'tick') desenharRuido(); });
desenharRuido();

// ===== Tempos do topo (foco, pausa e meta de ciclos) =====
Object.keys(P.tempos).forEach(nome => {
    const campo = document.getElementById(`cfg-${nome}`);
    campo.value = P.tempos[nome];
    campo.addEventListener('change', () => {
        const valor = parseInt(campo.value, 10);
        if (!(valor >= 1 && valor <= Number(campo.max))) {
            campo.value = P.tempos[nome];
            return;
        }
        P.definirTempo(nome, valor);
    });
});

atualizarTela();
