// =====================================================================
// Motor do pomodoro: funciona em TODAS as páginas do site.
//
// O estado (modo, tempo, ciclo...) fica salvo no navegador (localStorage).
// Como o tempo é calculado pelo relógio do computador, o pomodoro continua
// contando quando você troca de página ou até fecha a aba.
//
// As telas (página do pomodoro e o mini pomodoro do canto) só "escutam"
// o motor:  Pomodoro.ouvir(funcao)  e chamam  Pomodoro.iniciar(), etc.
// =====================================================================
window.Pomodoro = (() => {
    const CHAVE_ESTADO = 'pomodoro-estado';
    const CHAVE_TEMPOS = 'pomodoro-tempos';
    const CHAVE_ESCOLHA = 'pomodoro-escolha';
    const UM_MINUTO = 60 * 1000;
    const LIMITE_MS = 180 * UM_MINUTO;  // um foco registra no máximo 3h
    const TEMPOS_PADRAO = { foco: 25, pausa: 5, ciclos: 4 };
    const NOMES = { foco: 'Foco', pausa: 'Pausa' };

    // ----- tempos (foco, pausa, meta de ciclos) -----
    const salvos = JSON.parse(localStorage.getItem(CHAVE_TEMPOS) || '{}');
    const tempos = {
        foco: salvos.foco ?? TEMPOS_PADRAO.foco,
        pausa: salvos.pausa ?? salvos.pausa_curta ?? TEMPOS_PADRAO.pausa,  // aproveita a versão antiga
        ciclos: salvos.ciclos ?? TEMPOS_PADRAO.ciclos,
    };

    const hoje = () => new Date().toLocaleDateString('sv');  // "2026-11-02"
    const duracaoMs = modo => tempos[modo] * UM_MINUTO;

    function estadoNovo(focos = 0) {
        return {
            modo: 'foco',
            alvoMs: duracaoMs('foco'),  // quanto este bloco deve durar (cresce com +5 / +15)
            acumuladoMs: 0,             // tempo já passado antes do último "iniciar"
            inicioTrecho: null,         // quando apertou "iniciar" pela última vez
            rodando: false,
            livre: false,               // "seguir sem limite"
            avisou: false,              // já perguntou "ainda no foco?" neste bloco
            avisoFechado: false,        // clicou em "fazer a pausa"
            aguardando: false,          // o bloco acabou e o próximo espera você apertar "iniciar"
            focosConcluidos: focos,
            blocoId: Date.now(),        // identifica o bloco (evita registrar duas vezes)
            dia: hoje(),
        };
    }

    function ler() {
        try {
            return JSON.parse(localStorage.getItem(CHAVE_ESTADO));
        } catch {
            return null;
        }
    }

    let estado = ler() || estadoNovo();
    // Num dia novo, sem pomodoro rodando, a contagem de ciclos recomeça
    if (estado.dia !== hoje() && !estado.rodando && !estado.acumuladoMs) estado = estadoNovo();

    function salvar() {
        localStorage.setItem(CHAVE_ESTADO, JSON.stringify(estado));
    }

    // ----- quem está ouvindo (as telas) -----
    const ouvintes = new Set();
    function avisarTelas(tipo, dados) {
        ouvintes.forEach(funcao => funcao(tipo, dados));
    }

    // ----- contas de tempo -----
    function decorridoMs() {
        return estado.acumuladoMs + (estado.rodando ? Date.now() - estado.inicioTrecho : 0);
    }

    function restanteMs() {
        return estado.alvoMs - decorridoMs();
    }

    function emAndamento() {
        return estado.rodando || estado.acumuladoMs > 0 || estado.livre || estado.aguardando;
    }

    function mostrarAviso() {
        return estado.modo === 'foco' && estado.avisou && !estado.avisoFechado && !estado.livre;
    }

    function formatar(ms, arredondar = Math.ceil) {
        const totalSeg = arredondar(ms / 1000);
        const min = String(Math.floor(totalSeg / 60)).padStart(2, '0');
        const seg = String(totalSeg % 60).padStart(2, '0');
        return `${min}:${seg}`;
    }

    // Texto do relógio: "24:13", ou no modo livre o extra: "+03:20"
    function textoDoTempo() {
        const restante = restanteMs();
        return estado.livre && restante < 0 ? `+${formatar(-restante, Math.floor)}` : formatar(Math.max(0, restante));
    }

    function fracaoRestante() {
        return estado.livre ? 1 : Math.max(0, restanteMs()) / estado.alvoMs;
    }

    // Ciclo = um foco. Ex.: "ciclo 2 de 4"; ao bater a meta: "4 de 4 ciclos ✓"
    function textoDoCiclo() {
        const meta = tempos.ciclos;
        const feitos = estado.focosConcluidos;
        if (estado.modo === 'pausa') {
            return feitos >= meta ? `${feitos} de ${meta} ciclos ✓` : `${feitos} de ${meta} ciclos`;
        }
        const atual = feitos + 1;
        return atual > meta ? `ciclo ${atual} · meta batida ✓` : `ciclo ${atual} de ${meta}`;
    }

    // ----- ações -----
    function iniciar() {
        if (estado.rodando) return;
        prepararSom();
        pedirPermissaoDeNotificacao();
        estado.inicioTrecho = Date.now();
        estado.rodando = true;
        estado.aguardando = false;
        estado.dia = hoje();
        salvar();
        avisarTelas('mudou');
    }

    function pausar() {
        if (estado.rodando) {
            estado.acumuladoMs = decorridoMs();
            estado.rodando = false;
            salvar();
        }
        avisarTelas('mudou');
    }

    function alternar() {
        estado.rodando ? pausar() : iniciar();
    }

    function trocarModo(novo) {
        const focos = estado.focosConcluidos;
        estado = estadoNovo(focos);
        estado.modo = novo;
        estado.alvoMs = duracaoMs(novo);
        salvar();
        avisarTelas('mudou');
    }

    const proximoModo = () => (estado.modo === 'foco' ? 'pausa' : 'foco');

    function pular() {  // não conta como pomodoro concluído
        trocarModo(proximoModo());
    }

    function recomecar() {
        trocarModo(estado.modo);
    }

    function estender(minutos) {
        estado.alvoMs = Math.min(estado.alvoMs + minutos * UM_MINUTO, LIMITE_MS);
        estado.avisou = false;  // pergunta de novo 1 minuto antes do novo fim
        estado.avisoFechado = false;
        salvar();
        avisarTelas('mudou');
    }

    function seguirSemLimite() {
        estado.livre = true;
        salvar();
        avisarTelas('mudou');
    }

    // ■ Encerrar antes do tempo: salva o foco feito até agora e para o pomodoro.
    // Não começa a pausa: se você encerrou, o pomodoro não emenda nada.
    function minutosFeitos() {
        return Math.round(Math.min(decorridoMs(), LIMITE_MS) / UM_MINUTO);
    }

    function textoParaEncerrar() {
        if (estado.modo !== 'foco') return 'Encerrar a pausa e parar o pomodoro?';
        const minutos = minutosFeitos();
        return minutos >= 1
            ? `Encerrar agora? ${minutos} min de foco serão registrados.`
            : 'Encerrar agora? Com menos de 1 minuto, nada será registrado.';
    }

    function finalizar() {
        const eraFoco = estado.modo === 'foco';
        const minutos = minutosFeitos();
        if (eraFoco && minutos >= 1) estado.focosConcluidos++;
        trocarModo('foco');  // volta ao início, parado (a contagem de ciclos continua)
        if (eraFoco && minutos >= 1) registrarSessao(minutos);
    }

    // ✕ do mini pomodoro: dispensa o bloco que estava esperando
    function dispensar() {
        estado.aguardando = false;
        salvar();
        avisarTelas('mudou');
    }

    function fecharAviso() {
        estado.avisoFechado = true;
        salvar();
        avisarTelas('mudou');
    }

    // Começa o bloco "voltando no tempo": como se tivesse começado em `desde`.
    // Usado quando o fim do bloco anterior foi percebido com atraso.
    function iniciarDesde(desde) {
        iniciar();
        estado.inicioTrecho = Math.min(desde, Date.now());
        salvar();
    }

    function terminar() {
        // Se outra aba já terminou este bloco, só sincroniza
        const noNavegador = ler();
        if (noNavegador && noNavegador.blocoId !== estado.blocoId) {
            estado = noNavegador;
            avisarTelas('mudou');
            return;
        }

        const decorrido = decorridoMs();
        // Quando o bloco deveria ter acabado. O navegador pode perceber o fim com atraso
        // (página em segundo plano só confere o relógio ~1x por minuto, ou site fechado).
        const fimPrevisto = estado.livre ? Date.now()
            : (estado.rodando ? estado.inicioTrecho + (estado.alvoMs - estado.acumuladoMs) : Date.now());
        const atraso = Math.max(0, Date.now() - fimPrevisto);
        // tempo real focado: no modo livre, tudo (até 3h); senão, no máximo o previsto
        const focado = estado.livre ? Math.min(decorrido, LIMITE_MS) : Math.min(decorrido, estado.alvoMs);
        const minutos = Math.max(1, Math.round(focado / UM_MINUTO));
        const eraFoco = estado.modo === 'foco';

        if (eraFoco) estado.focosConcluidos++;
        trocarModo(proximoModo());

        const tocou = tocarSom('fim');
        notificar(eraFoco ? 'Foco concluído!' : 'Pausa acabou!',
                  eraFoco ? `${minutos} min de foco registrados. Hora da pausa.` : 'Bora para o próximo foco.');
        if (eraFoco) registrarSessao(minutos);

        // Automático: o próximo bloco começa contando a partir de quando o anterior acabou.
        // Ex.: o foco acabou há 1 min (aba em segundo plano) → a pausa já aparece com 4 min.
        const metaBatida = estado.modo === 'foco' && estado.focosConcluidos >= tempos.ciclos;
        const esperar = () => { estado.aguardando = true; salvar(); };  // mini fica visível, esperando você

        if (metaBatida) {
            esperar();
        } else if (estado.modo === 'pausa') {
            if (atraso < estado.alvoMs) {
                iniciarDesde(fimPrevisto);
            } else {
                // a pausa inteira também já passou (você não estava aqui): espera no próximo foco
                trocarModo('foco');
                esperar();
            }
        } else if (atraso < 2 * UM_MINUTO) {
            iniciarDesde(fimPrevisto);  // pausa acabou há pouco: o foco segue automático
        } else {
            esperar();  // pausa acabou faz tempo: não inventa um foco que você não fez
        }
        if (!tocou) deixarSomPendente('fim');  // depois de trocar de bloco (o estado novo apaga o antigo)
        avisarTelas('fim', { eraFoco, minutos });
    }

    function tick() {
        tocarSomPendente();
        atualizarRuido();  // liga no foco, desliga na pausa (em até 1/4 de segundo)
        if (!estado.rodando) return;
        const restante = restanteMs();

        // 1 minuto antes do fim do foco: pergunta se quer continuar
        if (estado.modo === 'foco' && !estado.livre && !estado.avisou
            && restante <= UM_MINUTO && estado.alvoMs > UM_MINUTO) {
            estado.avisou = true;
            salvar();
            tocarOuDeixarPendente('aviso');
            notificar('Ainda no foco?', 'Falta 1 minuto. Quer continuar estudando ou fazer a pausa?');
        }

        const acabou = estado.livre ? decorridoMs() >= LIMITE_MS : restante <= 0;
        if (acabou) {
            terminar();
        } else {
            avisarTelas('tick');
        }
    }

    // ----- tempos -----
    function definirTempo(nome, valor) {
        tempos[nome] = valor;
        localStorage.setItem(CHAVE_TEMPOS, JSON.stringify(tempos));
        // sem pomodoro em andamento, o relógio já mostra o tempo novo
        if (nome === estado.modo && !emAndamento()) {
            estado.alvoMs = duracaoMs(nome);
            salvar();
        }
        avisarTelas('mudou');
    }

    // ----- registrar a sessão no Django -----
    // Usa a escolha feita na página do pomodoro (disciplina/tópico ou projeto/funcionalidade)
    function escolhaAtual() {
        const escolha = JSON.parse(localStorage.getItem(CHAVE_ESCOLHA) || '{}');
        const principal = escolha.disciplina || '';
        const dados = { tarefa: escolha.tarefa || '' };
        if (principal.startsWith('p:')) {
            dados.projeto_id = principal.slice(2);
            dados.funcionalidade_id = escolha.topico || null;
        } else {
            dados.disciplina_id = principal || null;
            dados.topico_id = escolha.topico || null;
        }
        return dados;
    }

    async function registrarSessao(minutos) {
        const config = document.getElementById('pomodoro-config')?.dataset;
        if (!config) return;
        try {
            const resposta = await fetch(config.urlRegistrar, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': config.csrf },
                body: JSON.stringify({ duracao_minutos: minutos, ...escolhaAtual() }),
            });
            if (!resposta.ok) throw new Error(resposta.status);
            avisarTelas('sessao', await resposta.json());
        } catch (erro) {
            console.error('Não consegui salvar a sessão:', erro);
        }
    }

    // ----- som -----
    // O navegador só deixa tocar som numa página depois de um clique nela.
    let audio = null;
    let volumeGeral = null;

    function prepararSom() {
        try {
            if (!audio) {
                audio = new AudioContext();
                // quando o som for liberado (ou bloqueado), as telas atualizam o aviso 🔇
                audio.addEventListener('statechange', () => avisarTelas('mudou'));
            }
            if (audio.state === 'suspended') audio.resume();
        } catch { /* navegador sem som */ }
    }
    // Tenta já ao abrir a página (alguns navegadores deixam) e a cada clique/tecla até conseguir.
    prepararSom();
    document.addEventListener('pointerdown', () => { if (!somLiberado()) prepararSom(); });
    document.addEventListener('keydown', () => { if (!somLiberado()) prepararSom(); });

    const somLiberado = () => Boolean(audio) && audio.state === 'running';

    // Um "sininho": nota principal + dois harmônicos mais baixos que somem devagar
    const MELODIAS = {
        fim: { notas: [659.25, 783.99, 1046.5], volume: 0.32, repetir: 3 },   // mi-sol-dó, 3 vezes
        aviso: { notas: [783.99, 1046.5], volume: 0.18, repetir: 1 },          // curtinho e baixo
    };

    function nota(frequencia, inicio, volume) {
        const duracao = 1.4;
        [[1, 1], [2, 0.3], [3, 0.08]].forEach(([multiplo, peso]) => {
            const osc = audio.createOscillator();
            const ganho = audio.createGain();
            osc.frequency.value = frequencia * multiplo;
            ganho.gain.setValueAtTime(0.0001, inicio);
            ganho.gain.exponentialRampToValueAtTime(volume * peso, inicio + 0.012);
            ganho.gain.exponentialRampToValueAtTime(0.0001, inicio + duracao / multiplo);
            osc.connect(ganho).connect(volumeGeral);
            osc.start(inicio);
            osc.stop(inicio + duracao);
        });
    }

    function tocarSom(tipo) {
        if (!somLiberado()) return false;
        if (!volumeGeral) {
            volumeGeral = audio.createGain();
            volumeGeral.gain.value = 0.8;
            volumeGeral.connect(audio.destination);
        }
        const { notas, volume, repetir } = MELODIAS[tipo];
        for (let vez = 0; vez < repetir; vez++) {
            notas.forEach((frequencia, i) => nota(frequencia, audio.currentTime + vez * 1.1 + i * 0.16, volume));
        }
        return true;
    }

    // Som "pendente": a aba que percebeu o fim do bloco pode não ter permissão para tocar
    // (por exemplo, recarregada e ainda sem clique). Ela deixa o som anotado no estado e
    // qualquer outra aba liberada toca. Só vale por 2 minutos, para não tocar atrasado.
    function deixarSomPendente(tipo) {
        estado.somPendente = { tipo, em: Date.now() };
        salvar();
    }

    function tocarOuDeixarPendente(tipo) {
        if (!tocarSom(tipo)) deixarSomPendente(tipo);
    }

    function tocarSomPendente() {
        const pendente = estado.somPendente;
        if (!pendente) return;
        if (Date.now() - pendente.em > 2 * UM_MINUTO) {
            estado.somPendente = null;  // velho demais: descarta
            salvar();
        } else if (somLiberado()) {
            estado.somPendente = null;  // salva antes de tocar: as outras abas não tocam de novo
            salvar();
            tocarSom(pendente.tipo);
        }
    }

    // ----- ruído (branco, rosa ou marrom) tocando junto com o foco -----
    // Não usa arquivo de áudio: o navegador gera 8 s de números aleatórios e toca em loop.
    // Só toca com o FOCO rodando (a pausa fica em silêncio). Com várias abas abertas, só uma
    // toca: a "dona" do ruído, que avisa a cada segundo no localStorage que continua tocando.
    const CHAVE_RUIDO = 'pomodoro-ruido';
    const CHAVE_DONA_RUIDO = 'pomodoro-ruido-aba';
    const TIPOS_DE_RUIDO = ['branco', 'rosa', 'marrom'];
    const ruido = { ligado: false, tipo: 'marrom', volume: 0.4 };
    try { Object.assign(ruido, JSON.parse(localStorage.getItem(CHAVE_RUIDO) || '{}')); } catch { /* ignora */ }
    const minhaAba = Math.random().toString(36).slice(2);
    const ruidosProntos = {};  // o som de cada tipo é gerado uma vez só
    let fonteRuido = null;
    let volumeRuido = null;
    let tipoTocando = null;

    function gerarRuido(tipo) {
        const taxa = audio.sampleRate;
        const total = taxa * 8;
        const emenda = Math.round(taxa / 2);  // meio segundo para o fim "colar" no começo sem estalo
        const bruto = new Float32Array(total + emenda);
        let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0, anterior = 0;
        for (let i = 0; i < bruto.length; i++) {
            const branco = Math.random() * 2 - 1;
            if (tipo === 'branco') {
                bruto[i] = branco * 0.35;
            } else if (tipo === 'rosa') {
                // filtro de Paul Kellet: tira um pouco dos agudos (som de chuva)
                b0 = 0.99886 * b0 + branco * 0.0555179; b1 = 0.99332 * b1 + branco * 0.0750759;
                b2 = 0.96900 * b2 + branco * 0.1538520; b3 = 0.86650 * b3 + branco * 0.3104856;
                b4 = 0.55000 * b4 + branco * 0.5329522; b5 = -0.7616 * b5 - branco * 0.0168980;
                bruto[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + branco * 0.5362) * 0.09;
                b6 = branco * 0.115926;
            } else {
                // marrom: cada valor anda um pouquinho a partir do anterior (som grave, de cachoeira)
                anterior = (anterior + 0.02 * branco) / 1.02;
                bruto[i] = anterior * 3.5;
            }
        }
        const buffer = audio.createBuffer(1, total, taxa);
        const saida = buffer.getChannelData(0);
        saida.set(bruto.subarray(0, total));
        // o começo vai virando o pedaço que vem logo depois do fim: o loop não dá "clique"
        for (let i = 0; i < emenda; i++) {
            const t = i / emenda;
            saida[i] = bruto[i] * Math.sqrt(t) + bruto[total + i] * Math.sqrt(1 - t);
        }
        return buffer;
    }

    // Volume do controle (0 a 1) → volume do som. Ao quadrado: o ouvido percebe melhor assim.
    const ganhoDoRuido = () => 0.6 * ruido.volume ** 2;

    function comecarRuido() {
        pararRuido();
        ruidosProntos[ruido.tipo] ??= gerarRuido(ruido.tipo);
        volumeRuido = audio.createGain();
        volumeRuido.gain.value = 0;
        volumeRuido.connect(audio.destination);
        fonteRuido = audio.createBufferSource();
        fonteRuido.buffer = ruidosProntos[ruido.tipo];
        fonteRuido.loop = true;
        fonteRuido.connect(volumeRuido);
        fonteRuido.start();
        tipoTocando = ruido.tipo;
        volumeRuido.gain.setTargetAtTime(ganhoDoRuido(), audio.currentTime, 0.4);  // entra devagar
    }

    function pararRuido() {
        if (!fonteRuido) return;
        volumeRuido.gain.setTargetAtTime(0, audio.currentTime, 0.15);  // sai devagar
        fonteRuido.stop(audio.currentTime + 1);
        fonteRuido = volumeRuido = tipoTocando = null;
    }

    // O ruído deveria estar tocando agora (em alguma aba)?
    const ruidoNoFoco = () => ruido.ligado && estado.rodando && estado.modo === 'foco';

    function lerDona() {
        try { return JSON.parse(localStorage.getItem(CHAVE_DONA_RUIDO)); } catch { return null; }
    }

    // Esta aba pode tocar? Pode se ninguém está tocando (ou a outra aba sumiu há 5 s)
    function pegarRuido() {
        const dona = lerDona();
        const agora = Date.now();
        if (dona && dona.aba !== minhaAba && agora - dona.em < 5000) return false;
        if (!dona || dona.aba !== minhaAba || agora - dona.em > 1000) {
            localStorage.setItem(CHAVE_DONA_RUIDO, JSON.stringify({ aba: minhaAba, em: agora }));
        }
        return true;
    }

    function largarRuido() {
        if (lerDona()?.aba === minhaAba) localStorage.removeItem(CHAVE_DONA_RUIDO);
    }

    function atualizarRuido() {
        const tocar = ruidoNoFoco() && somLiberado() && pegarRuido();
        if (tocar && (!fonteRuido || tipoTocando !== ruido.tipo)) {
            comecarRuido();
        } else if (!tocar && fonteRuido) {
            pararRuido();
            largarRuido();
        }
    }

    function definirRuido(mudancas) {
        if (mudancas.tipo && !TIPOS_DE_RUIDO.includes(mudancas.tipo)) return;
        Object.assign(ruido, mudancas);
        ruido.volume = Math.min(1, Math.max(0, Number(ruido.volume) || 0));
        localStorage.setItem(CHAVE_RUIDO, JSON.stringify(ruido));
        if (ruido.ligado) prepararSom();  // o clique no botão já libera o som
        if (volumeRuido) volumeRuido.gain.setTargetAtTime(ganhoDoRuido(), audio.currentTime, 0.05);
        atualizarRuido();
        avisarTelas('mudou');
    }

    // Saindo da página: libera para a próxima página (ou outra aba) tocar
    window.addEventListener('pagehide', largarRuido);

    // ----- notificação do sistema -----
    function pedirPermissaoDeNotificacao() {
        if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
    }

    // Aparece se você está em outra aba/janela, ou se o som não pôde tocar nesta página
    function notificar(titulo, texto) {
        if (!('Notification' in window) || Notification.permission !== 'granted') return;
        if (!document.hidden && somLiberado()) return;
        const notificacao = new Notification(titulo, { body: texto, tag: 'studyhub-pomodoro' });
        notificacao.onclick = () => { window.focus(); notificacao.close(); };
    }

    // ----- outras abas -----
    // Se o pomodoro mudar em outra aba, esta aba se atualiza
    window.addEventListener('storage', evento => {
        if (evento.key === CHAVE_ESTADO && evento.newValue) {
            estado = JSON.parse(evento.newValue);
            avisarTelas('mudou');
        }
        if (evento.key === CHAVE_RUIDO && evento.newValue) {  // mexeu no ruído em outra aba
            Object.assign(ruido, JSON.parse(evento.newValue));
            if (volumeRuido) volumeRuido.gain.setTargetAtTime(ganhoDoRuido(), audio.currentTime, 0.05);
            avisarTelas('mudou');
        }
    });

    setInterval(tick, 250);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });

    return {
        NOMES, tempos, CHAVE_ESCOLHA,
        get estado() { return estado; },
        ouvir: funcao => ouvintes.add(funcao),
        iniciar, pausar, alternar, pular, recomecar, estender, seguirSemLimite, fecharAviso, dispensar,
        finalizar, textoParaEncerrar,
        encerrar: () => terminar(), definirTempo, tick,
        decorridoMs, textoDoTempo, textoDoCiclo, fracaoRestante, emAndamento, mostrarAviso, somLiberado,
        TIPOS_DE_RUIDO, definirRuido, ruidoNoFoco,
        get ruido() { return { ...ruido }; },
    };
})();
