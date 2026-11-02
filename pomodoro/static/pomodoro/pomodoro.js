// ===== Configuração =====
// Tempos em minutos e quantidade de ciclos (focos) até a pausa longa.
// Ficam salvos no navegador (localStorage).
const TEMPOS_PADRAO = { foco: 25, pausa_curta: 5, pausa_longa: 15, ciclos: 4 };
const NOMES = { foco: 'Foco', pausa_curta: 'Pausa curta', pausa_longa: 'Pausa longa' };

const tempos = { ...TEMPOS_PADRAO, ...JSON.parse(localStorage.getItem('pomodoro-tempos') || '{}') };

// ===== Elementos da página =====
const secao = document.querySelector('.pomodoro');
const card = document.querySelector('.relogio-card');
const elTempo = document.getElementById('tempo');
const elCiclo = document.getElementById('ciclo');
const anel = document.getElementById('anel');
const campoTarefa = document.getElementById('tarefa');
const btnIniciar = document.getElementById('btn-iniciar');
const botoesModo = document.querySelectorAll('.modo');
const selDisciplina = document.getElementById('disciplina');
const selTopico = document.getElementById('topico');

// Tópicos de cada disciplina, enviados pelo Django: { "3": [{id, nome}, ...], ... }
const TOPICOS = JSON.parse(document.getElementById('dados-topicos').textContent);

// Comprimento da borda do círculo (2 × π × raio), usado para desenhar o progresso
const CIRCUNFERENCIA = 2 * Math.PI * 90;
anel.style.strokeDasharray = CIRCUNFERENCIA;

// ===== Estado (o que o relógio "lembra") =====
let modo = 'foco';
let focosConcluidos = 0;
let rodando = false;
let restanteMs = tempos.foco * 60 * 1000;
let fimEm = null;      // momento exato em que o bloco termina
let intervalo = null;
let audio = null;

// ===== Funções =====
function duracaoMs(m) {
    return tempos[m] * 60 * 1000;
}

function formatar(ms) {
    const totalSeg = Math.ceil(ms / 1000);
    const min = String(Math.floor(totalSeg / 60)).padStart(2, '0');
    const seg = String(totalSeg % 60).padStart(2, '0');
    return `${min}:${seg}`;
}

function atualizarTela() {
    const texto = formatar(restanteMs);
    elTempo.textContent = texto;
    document.title = `${texto} · ${NOMES[modo]}`;  // aparece na aba do navegador

    const fracao = restanteMs / duracaoMs(modo);
    anel.style.strokeDashoffset = CIRCUNFERENCIA * (1 - fracao);

    elCiclo.textContent = `Ciclo ${(focosConcluidos % tempos.ciclos) + 1} de ${tempos.ciclos}`;
    btnIniciar.textContent = rodando ? 'Pausar' : 'Iniciar';

    botoesModo.forEach(b => b.classList.toggle('ativo', b.dataset.modo === modo));
    card.classList.toggle('pausa', modo !== 'foco');
}

function iniciar() {
    // O navegador só deixa tocar som depois de um clique, então preparamos aqui
    audio ??= new AudioContext();
    rodando = true;
    fimEm = Date.now() + restanteMs;
    // Em vez de "diminuir 1 por segundo", calculamos quanto falta até fimEm.
    // Assim o relógio não atrasa se o navegador deixar a aba mais lenta.
    intervalo = setInterval(tick, 250);
    atualizarTela();
}

function pausar() {
    rodando = false;
    clearInterval(intervalo);
    atualizarTela();
}

function tick() {
    restanteMs = Math.max(0, fimEm - Date.now());
    atualizarTela();
    if (restanteMs === 0) terminar();
}

function trocarModo(novo) {
    pausar();
    modo = novo;
    restanteMs = duracaoMs(modo);
    atualizarTela();
}

function proximoModo() {
    if (modo !== 'foco') return 'foco';
    return focosConcluidos % tempos.ciclos === 0 ? 'pausa_longa' : 'pausa_curta';
}

function terminar() {
    pausar();
    tocarSom();
    if (modo === 'foco') {
        focosConcluidos++;
        registrarSessao(tempos.foco);
    }
    trocarModo(proximoModo());
}

// Três "plins" suaves, gerados pelo próprio navegador (sem arquivo de áudio)
function tocarSom() {
    if (!audio) return;
    [0, 0.35, 0.7].forEach(atraso => {
        const t = audio.currentTime + atraso;
        const osc = audio.createOscillator();
        const volume = audio.createGain();
        osc.frequency.value = 880;
        volume.gain.setValueAtTime(0.0001, t);
        volume.gain.exponentialRampToValueAtTime(0.3, t + 0.02);
        volume.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
        osc.connect(volume).connect(audio.destination);
        osc.start(t);
        osc.stop(t + 0.3);
    });
}

// Envia a sessão concluída para o Django salvar no banco
async function registrarSessao(minutos) {
    try {
        const resposta = await fetch(secao.dataset.urlRegistrar, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': secao.dataset.csrf,  // proteção exigida pelo Django
            },
            body: JSON.stringify({
                duracao_minutos: minutos,
                disciplina_id: selDisciplina.value || null,
                topico_id: selTopico.value || null,
                tarefa: campoTarefa.value.trim(),
            }),
        });
        if (!resposta.ok) return;
        const dados = await resposta.json();
        adicionarNaLista(dados);
    } catch (erro) {
        console.error('Não consegui salvar a sessão:', erro);
    }
}

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

// ===== Escolha de disciplina e tópico =====
function preencherTopicos() {
    const topicos = TOPICOS[selDisciplina.value] || [];
    selTopico.replaceChildren(new Option('Sem tópico', ''));
    topicos.forEach(t => selTopico.add(new Option(t.nome, t.id)));
    selTopico.disabled = topicos.length === 0;
}

function lembrarEscolha() {
    localStorage.setItem('pomodoro-escolha', JSON.stringify({
        disciplina: selDisciplina.value,
        topico: selTopico.value,
    }));
}

selDisciplina.addEventListener('change', () => {
    preencherTopicos();
    lembrarEscolha();
});
selTopico.addEventListener('change', lembrarEscolha);

// Ao abrir a página, volta para a última disciplina/tópico usados (se ainda existirem)
const escolhaSalva = JSON.parse(localStorage.getItem('pomodoro-escolha') || '{}');
if (escolhaSalva.disciplina && TOPICOS[escolhaSalva.disciplina]) {
    selDisciplina.value = escolhaSalva.disciplina;
    preencherTopicos();
    if (TOPICOS[escolhaSalva.disciplina].some(t => String(t.id) === escolhaSalva.topico)) {
        selTopico.value = escolhaSalva.topico;
    }
}

// ===== Botões e teclado =====
btnIniciar.addEventListener('click', () => (rodando ? pausar() : iniciar()));

document.getElementById('btn-reiniciar').addEventListener('click', () => trocarModo(modo));

// Pular não conta como pomodoro concluído
document.getElementById('btn-pular').addEventListener('click', () => {
    trocarModo(modo === 'foco' ? 'pausa_curta' : 'foco');
});

botoesModo.forEach(botao => {
    botao.addEventListener('click', () => trocarModo(botao.dataset.modo));
});

document.addEventListener('keydown', evento => {
    const digitando = ['INPUT', 'SELECT'].includes(evento.target.tagName);
    if (evento.code === 'Space' && !digitando) {
        evento.preventDefault();
        rodando ? pausar() : iniciar();
    }
});

// Campos de configuração (tempos e ciclos)
Object.keys(TEMPOS_PADRAO).forEach(m => {
    const campo = document.getElementById(`cfg-${m}`);
    campo.value = tempos[m];
    campo.addEventListener('change', () => {
        const valor = parseInt(campo.value, 10);
        if (!(valor >= 1 && valor <= Number(campo.max))) {
            campo.value = tempos[m];
            return;
        }
        tempos[m] = valor;
        localStorage.setItem('pomodoro-tempos', JSON.stringify(tempos));
        if (m === 'ciclos') {
            focosConcluidos = 0;  // recomeça a contagem com o novo total
        } else if (!rodando && m === modo) {
            restanteMs = duracaoMs(modo);
        }
        atualizarTela();
    });
});

// Avisa antes de fechar a aba com o relógio rodando
window.addEventListener('beforeunload', evento => {
    if (rodando) evento.preventDefault();
});

atualizarTela();
