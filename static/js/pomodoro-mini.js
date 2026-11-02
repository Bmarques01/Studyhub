// Mini pomodoro no canto da tela: aparece nas outras páginas enquanto um pomodoro
// está em andamento. Só mostra o estado do motor (pomodoro-motor.js) e chama as ações dele.
const mini = document.getElementById('mini-pomodoro');

if (mini && window.Pomodoro) {
    const P = window.Pomodoro;
    const anel = document.getElementById('mini-anel');
    const CIRCUNFERENCIA = 2 * Math.PI * 17;
    anel.style.strokeDasharray = CIRCUNFERENCIA;

    const el = id => document.getElementById(id);
    let recado = null;  // texto temporário, ex.: "✓ 25 min registrados"

    function desenhar() {
        const estado = P.estado;
        mini.hidden = !P.emAndamento();
        if (mini.hidden) return;

        const esperando = estado.aguardando && !estado.rodando;
        el('mini-modo').textContent = P.NOMES[estado.modo].toLowerCase() + (esperando ? ' · pronta pra começar' : '');
        el('mini-tempo').textContent = P.textoDoTempo();
        el('mini-ciclo').textContent = recado || P.textoDoCiclo();
        anel.style.strokeDashoffset = CIRCUNFERENCIA * (1 - P.fracaoRestante());

        mini.classList.toggle('pausa', estado.modo === 'pausa');
        mini.classList.toggle('parado', !estado.rodando);
        el('mini-icone-pausar').hidden = !estado.rodando;
        el('mini-icone-continuar').hidden = estado.rodando;
        el('mini-alternar').title = estado.rodando ? 'Pausar' : 'Continuar';
        el('mini-aviso').hidden = !P.mostrarAviso();
        el('mini-livre').hidden = !estado.livre;
        el('mini-fechar').hidden = !esperando;
    }

    P.ouvir((tipo, dados) => {
        if (tipo === 'sessao') {
            recado = `✓ ${dados.duracao_minutos} min registrados`;
            setTimeout(() => { recado = null; desenhar(); }, 5000);
        }
        desenhar();
    });

    el('mini-alternar').addEventListener('click', P.alternar);
    el('mini-pular').addEventListener('click', P.pular);
    el('mini-livre-btn').addEventListener('click', P.seguirSemLimite);
    el('mini-fazer-pausa').addEventListener('click', P.fecharAviso);
    el('mini-encerrar').addEventListener('click', P.encerrar);
    el('mini-fechar').addEventListener('click', P.dispensar);
    mini.querySelectorAll('[data-estender]').forEach(botao => {
        botao.addEventListener('click', () => P.estender(Number(botao.dataset.estender)));
    });

    desenhar();
}
