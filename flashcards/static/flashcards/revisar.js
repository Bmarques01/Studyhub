// Tela de revisão dos flashcards.
// O servidor decide qual cartão vem a seguir (memoria.py); aqui só mostramos e enviamos a nota.
// Atalhos: espaço/enter = mostrar resposta; 1 a 4 = de novo / difícil / bom / fácil.

const revisao = document.getElementById('revisao');
const config = revisao.dataset;
const el = id => document.getElementById(id);

let atual = null;        // o cartão na tela
let revelado = false;    // a resposta já apareceu?
let enviando = false;    // evita mandar a mesma nota duas vezes
let mostradoEm = 0;      // para medir quanto tempo você levou

function mostrar(dados) {
    el('restantes').textContent = dados.restantes;
    atual = dados.cartao;
    revelado = false;

    if (!atual) {
        el('palco').hidden = true;
        el('fim').hidden = false;
        el('fim-proxima').textContent = dados.proxima
            ? `O próximo cartão volta em ${dados.proxima}.`
            : 'Não há cartões agendados.';
        return;
    }

    // textContent: o texto do cartão aparece como texto, nunca vira HTML
    el('cartao-frente').textContent = atual.frente;
    el('cartao-verso').textContent = atual.verso;
    el('cartao-onde').textContent = atual.topico ? `${atual.disciplina} · ${atual.topico}` : atual.disciplina;
    el('cartao-cor').style.background = atual.cor;
    el('cartao-novo').hidden = !atual.novo;
    document.querySelectorAll('[data-nota]').forEach(botao => {
        botao.querySelector('[data-intervalo]').textContent = atual.intervalos[botao.dataset.nota];
    });

    el('area-verso').hidden = true;
    el('notas').hidden = true;
    el('btn-mostrar').hidden = false;
    el('palco').hidden = false;
    el('fim').hidden = true;
    mostradoEm = Date.now();
}

function revelar() {
    if (!atual || revelado) return;
    revelado = true;
    el('area-verso').hidden = false;
    el('notas').hidden = false;
    el('btn-mostrar').hidden = true;
}

function avisarErro(texto) {
    el('erro').textContent = texto;
    el('erro').hidden = false;
}

async function pedir(url, opcoes) {
    try {
        const resposta = await fetch(url, opcoes);
        if (!resposta.ok) throw new Error(resposta.status);
        el('erro').hidden = true;
        mostrar(await resposta.json());
    } catch (erro) {
        console.error(erro);
        avisarErro('Não consegui falar com o servidor. Confira se o runserver está rodando e tente de novo.');
    }
}

async function responder(nota) {
    if (!atual || !revelado || enviando) return;
    enviando = true;
    document.activeElement?.blur();  // tira o foco do botão clicado (senão o Enter clicaria nele de novo)
    await pedir(config.urlResponder.replace('/0/', `/${atual.id}/`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': config.csrf },
        body: JSON.stringify({
            nota,
            duracao_segundos: Math.round((Date.now() - mostradoEm) / 1000),
            disciplina: config.disciplina,
            topico: config.topico,  // revisando um baralho só
        }),
    });
    enviando = false;
}

el('btn-mostrar').addEventListener('click', revelar);
document.querySelectorAll('[data-nota]').forEach(botao => {
    botao.addEventListener('click', () => responder(Number(botao.dataset.nota)));
});

document.addEventListener('keydown', evento => {
    if (evento.repeat || evento.ctrlKey || evento.altKey || evento.metaKey) return;
    if (evento.target.closest('input, textarea, select')) return;  // digitando em outro lugar
    if (evento.key === ' ' || evento.key === 'Enter') {
        // Só quando o foco está "solto" na página ou no cartão: assim o Enter continua
        // funcionando nos links, no mini pomodoro e nos botões de nota (navegando pelo Tab).
        const alvo = evento.target;
        if (alvo !== document.body && !el('palco').contains(alvo)) return;
        if (alvo.closest('[data-nota]')) return;
        evento.preventDefault();  // o espaço não rola a página
        revelar();
    } else if (['1', '2', '3', '4'].includes(evento.key)) {
        responder(Number(evento.key));
    }
});

pedir(config.urlProximo);
