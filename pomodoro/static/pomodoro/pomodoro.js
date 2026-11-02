// ===== Configuração =====
// Tempos em minutos e quantidade de ciclos (focos) até a pausa longa.
// Ficam salvos no navegador (localStorage).
const TEMPOS_PADRAO = { foco: 25, pausa_curta: 5, pausa_longa: 15, ciclos: 4 };
const NOMES = { foco: 'Foco', pausa_curta: 'Pausa', pausa_longa: 'Pausa longa' };

const tempos = { ...TEMPOS_PADRAO, ...JSON.parse(localStorage.getItem('pomodoro-tempos') || '{}') };

// ===== Elementos da página =====
const secao = document.querySelector('.pomodoro');
const card = document.querySelector('.relogio-card');
const elTempo = document.getElementById('tempo');
const elCiclo = document.getElementById('ciclo');
const anel = document.getElementById('anel');
const campoTarefa = document.getElementById('tarefa');
const btnIniciar = document.getElementById('btn-iniciar');
const elModo = document.getElementById('modo-atual');
const selDisciplina = document.getElementById('disciplina');
const selTopico = document.getElementById('topico');

// Tópicos de cada disciplina, enviados pelo Django: { "3": [{id, nome}, ...], ... }
const TOPICOS = JSON.parse(document.getElementById('dados-topicos').textContent);

// Comprimento da borda do círculo (2 × π × raio), usado para desenhar o progresso
const CIRCUNFERENCIA = 2 * Math.PI * 90;
anel.style.strokeDasharray = CIRCUNFERENCIA;

// Precisam vir antes do estado, que já usa duracaoMs() (e ela usa UM_MINUTO)
const UM_MINUTO = 60 * 1000;
const LIMITE_MS = 180 * UM_MINUTO;  // um foco registra no máximo 3h

// ===== Estado (o que o relógio "lembra") =====
let modo = 'foco';
let focosConcluidos = 0;
let rodando = false;
let alvoMs = duracaoMs('foco');  // quanto este bloco deve durar (cresce com +5 / +15 min)
let acumuladoMs = 0;             // tempo já passado antes da última vez que apertou "iniciar"
let inicioTrecho = null;         // momento em que apertou "iniciar" pela última vez
let livre = false;               // "seguir sem limite": conta o tempo extra até encerrar
let avisou = false;              // já perguntou "ainda no foco?" neste bloco
let intervalo = null;
let audio = null;

// Elementos do aviso "ainda no foco?"
const aviso = document.getElementById('aviso-foco');
const barraLivre = document.getElementById('foco-livre');

// ===== Funções =====
function duracaoMs(m) {
    return tempos[m] * UM_MINUTO;
}

function formatar(ms, arredondar = Math.ceil) {
    const totalSeg = arredondar(ms / 1000);
    const min = String(Math.floor(totalSeg / 60)).padStart(2, '0');
    const seg = String(totalSeg % 60).padStart(2, '0');
    return `${min}:${seg}`;
}

// Em vez de "diminuir 1 por segundo", calculamos pelo relógio do computador.
// Assim o tempo não atrasa se o navegador deixar a aba mais lenta.
function decorridoMs() {
    return acumuladoMs + (rodando ? Date.now() - inicioTrecho : 0);
}

function atualizarTela() {
    const restante = alvoMs - decorridoMs();
    // No modo livre, depois do tempo previsto mostra o extra: "+03:20"
    const texto = livre && restante < 0 ? `+${formatar(-restante, Math.floor)}` : formatar(Math.max(0, restante));
    elTempo.textContent = texto;
    document.title = `${texto} · ${NOMES[modo]}`;  // aparece na aba do navegador

    const fracao = livre ? 1 : Math.max(0, restante) / alvoMs;
    anel.style.strokeDashoffset = CIRCUNFERENCIA * (1 - fracao);

    elCiclo.textContent = `Ciclo ${(focosConcluidos % tempos.ciclos) + 1} de ${tempos.ciclos}`;
    btnIniciar.textContent = rodando ? 'Pausar' : (decorridoMs() > 0 ? 'Continuar' : 'Iniciar');

    elModo.textContent = NOMES[modo].toLowerCase();
    card.classList.toggle('pausa', modo !== 'foco');
    card.classList.toggle('livre', livre);
    barraLivre.hidden = !livre;
}

function iniciar() {
    if (rodando) return;
    // O navegador só deixa tocar som depois de um clique, então preparamos aqui
    audio ??= new AudioContext();
    pedirPermissaoDeNotificacao();
    inicioTrecho = Date.now();
    rodando = true;
    intervalo = setInterval(tick, 250);
    atualizarTela();
}

function pausar() {
    if (rodando) {
        acumuladoMs = decorridoMs();
        rodando = false;
        clearInterval(intervalo);
    }
    atualizarTela();
}

function tick() {
    const restante = alvoMs - decorridoMs();

    // 1 minuto antes do fim do foco: pergunta se quer continuar
    if (modo === 'foco' && !livre && !avisou && restante <= UM_MINUTO && alvoMs > UM_MINUTO) {
        perguntarSeContinua();
    }

    const acabou = livre ? decorridoMs() >= LIMITE_MS : restante <= 0;
    if (acabou) {
        terminar();
    } else {
        atualizarTela();
    }
}

function trocarModo(novo) {
    pausar();
    modo = novo;
    alvoMs = duracaoMs(modo);
    acumuladoMs = 0;
    livre = false;
    avisou = false;
    aviso.hidden = true;
    atualizarTela();
}

function proximoModo() {
    if (modo !== 'foco') return 'foco';
    return focosConcluidos % tempos.ciclos === 0 ? 'pausa_longa' : 'pausa_curta';
}

function terminar() {
    // registra o tempo que você realmente focou (pode ser mais que o previsto)
    const minutos = Math.max(1, Math.round(Math.min(decorridoMs(), LIMITE_MS) / UM_MINUTO));
    pausar();
    tocarSom('fim');
    if (modo === 'foco') {
        focosConcluidos++;
        registrarSessao(minutos);
    }
    trocarModo(proximoModo());
}

// ===== "Ainda no foco?" =====
function perguntarSeContinua() {
    avisou = true;
    aviso.hidden = false;
    tocarSom('aviso');  // versão curta e mais baixa
    notificar();
}

function estender(minutos) {
    alvoMs = Math.min(alvoMs + minutos * UM_MINUTO, LIMITE_MS);
    avisou = false;  // pergunta de novo 1 minuto antes do novo fim
    aviso.hidden = true;
    atualizarTela();
}

function seguirSemLimite() {
    livre = true;
    aviso.hidden = true;
    atualizarTela();
}

function pedirPermissaoDeNotificacao() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

// Notificação do sistema, só quando você está em outra aba ou janela
function notificar() {
    if (!document.hidden || !('Notification' in window) || Notification.permission !== 'granted') return;
    const notificacao = new Notification('Ainda no foco?', {
        body: 'Falta 1 minuto. Quer continuar estudando ou fazer a pausa?',
        tag: 'studyhub-foco',
    });
    notificacao.onclick = () => {
        window.focus();
        notificacao.close();
    };
}

// ===== Som =====
// Um "sininho" gerado pelo próprio navegador (sem arquivo de áudio).
// Cada nota soma o som principal com dois harmônicos mais baixos, que somem devagar:
// fica com cara de sino/marimba, mais presente que um bipe, sem ser estridente.
const MELODIAS = {
    // mi → sol → dó, subindo; tocada 2 vezes no fim de um bloco
    fim: { notas: [659.25, 783.99, 1046.5], volume: 0.32, repetir: 2 },
    // sol → dó, curtinha e mais baixa, para o aviso de 1 minuto
    aviso: { notas: [783.99, 1046.5], volume: 0.18, repetir: 1 },
};

let volumeGeral = null;

function nota(frequencia, inicio, volume) {
    const duracao = 1.4;
    [[1, 1], [2, 0.3], [3, 0.08]].forEach(([multiplo, peso]) => {
        const osc = audio.createOscillator();
        const ganho = audio.createGain();
        osc.frequency.value = frequencia * multiplo;
        ganho.gain.setValueAtTime(0.0001, inicio);
        ganho.gain.exponentialRampToValueAtTime(volume * peso, inicio + 0.012);  // ataque rápido
        ganho.gain.exponentialRampToValueAtTime(0.0001, inicio + duracao / multiplo);  // some devagar
        osc.connect(ganho).connect(volumeGeral);
        osc.start(inicio);
        osc.stop(inicio + duracao);
    });
}

function tocarSom(tipo = 'fim') {
    if (!audio) return;
    if (!volumeGeral) {
        volumeGeral = audio.createGain();
        volumeGeral.gain.value = 0.8;
        volumeGeral.connect(audio.destination);
    }
    const { notas, volume, repetir } = MELODIAS[tipo];
    for (let vez = 0; vez < repetir; vez++) {
        notas.forEach((frequencia, i) => {
            nota(frequencia, audio.currentTime + vez * 1.1 + i * 0.16, volume);
        });
    }
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

// Ao abrir a página: se veio de "estudar agora" numa disciplina, usa ela;
// senão, volta para a última disciplina/tópico usados (se ainda existirem)
const escolhaSalva = JSON.parse(localStorage.getItem('pomodoro-escolha') || '{}');
if (secao.dataset.disciplinaInicial) {
    selDisciplina.value = secao.dataset.disciplinaInicial;
    preencherTopicos();
    lembrarEscolha();
} else if (escolhaSalva.disciplina && TOPICOS[escolhaSalva.disciplina]) {
    selDisciplina.value = escolhaSalva.disciplina;
    preencherTopicos();
    if (TOPICOS[escolhaSalva.disciplina].some(t => String(t.id) === escolhaSalva.topico)) {
        selTopico.value = escolhaSalva.topico;
    }
}

// ===== Botões e teclado =====
btnIniciar.addEventListener('click', () => (rodando ? pausar() : iniciar()));

document.getElementById('btn-reiniciar').addEventListener('click', () => trocarModo(modo));

// Botões do aviso "ainda no foco?" e do modo livre
document.querySelectorAll('[data-estender]').forEach(botao => {
    botao.addEventListener('click', () => estender(Number(botao.dataset.estender)));
});
document.getElementById('btn-livre').addEventListener('click', seguirSemLimite);
document.getElementById('btn-fazer-pausa').addEventListener('click', () => { aviso.hidden = true; });
document.getElementById('btn-encerrar').addEventListener('click', terminar);

// Pular não conta como pomodoro concluído
document.getElementById('btn-pular').addEventListener('click', () => {
    trocarModo(modo === 'foco' ? 'pausa_curta' : 'foco');
});

// Botão do sino: toca o som do alarme para você ouvir como é
document.getElementById('btn-testar-som').addEventListener('click', () => {
    audio ??= new AudioContext();
    tocarSom('fim');
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
        } else if (!rodando && m === modo && !livre) {
            alvoMs = duracaoMs(modo);
            acumuladoMs = 0;
        }
        atualizarTela();
    });
});

// Avisa antes de fechar a aba com o relógio rodando
window.addEventListener('beforeunload', evento => {
    if (rodando) evento.preventDefault();
});

atualizarTela();
