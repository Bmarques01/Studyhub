// Balãozinho (tooltip) dos gráficos.
// Qualquer elemento com data-tip-titulo mostra um balão ao passar o mouse ou focar com o teclado.

const balao = document.createElement('div');
balao.className = 'tooltip';
balao.hidden = true;
document.body.appendChild(balao);

const COR_ATUAL = '#e0609a';
const COR_ANTERIOR = '#8f6fd8';

// Uma linha do balão: [chave colorida] VALOR  nome
function linha(valor, nome, cor) {
    const el = document.createElement('div');
    el.className = 'tooltip-linha';
    if (cor) {
        const chave = document.createElement('i');
        chave.style.background = cor;
        el.appendChild(chave);
    }
    const forte = document.createElement('strong');
    forte.textContent = valor;  // textContent: texto puro, nunca vira código
    el.appendChild(forte);
    if (nome) {
        const span = document.createElement('span');
        span.textContent = nome;
        el.appendChild(span);
    }
    return el;
}

function mostrar(alvo) {
    const d = alvo.dataset;
    const titulo = document.createElement('span');
    titulo.className = 'tooltip-titulo';
    titulo.textContent = d.tipTitulo;
    balao.replaceChildren(titulo);

    if (d.tipAtual !== undefined) {
        // coluna do gráfico da semana: mostra as duas semanas juntas
        balao.append(
            linha(d.tipAtual, 'esta semana', COR_ATUAL),
            linha(d.tipAnterior, 'semana passada', COR_ANTERIOR),
        );
    } else {
        balao.append(linha(d.tipValor, 'estudados'));
    }

    // posiciona acima do elemento, centralizado
    const caixa = alvo.getBoundingClientRect();
    balao.style.left = `${caixa.left + caixa.width / 2 + window.scrollX}px`;
    balao.style.top = `${caixa.top + window.scrollY}px`;
    balao.hidden = false;
}

function esconder() {
    balao.hidden = true;
}

document.addEventListener('pointerover', evento => {
    const alvo = evento.target.closest('[data-tip-titulo]');
    alvo ? mostrar(alvo) : esconder();
});
document.addEventListener('focusin', evento => {
    const alvo = evento.target.closest('[data-tip-titulo]');
    if (alvo) mostrar(alvo);
});
document.addEventListener('focusout', esconder);
document.addEventListener('scroll', esconder, { passive: true });
