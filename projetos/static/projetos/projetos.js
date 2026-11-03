// Kanban: arrastar e soltar cartões entre as colunas.
// Ao soltar, avisa o Django da nova coluna e da nova ordem dos cartões.

const pagina = document.querySelector('.projeto-pagina');
let arrastado = null;
let origem = null;  // de onde o cartão saiu: lista e vizinho de baixo (para devolver ao lugar)

document.querySelectorAll('.cartao').forEach(cartao => {
    cartao.addEventListener('dragstart', evento => {
        arrastado = cartao;
        origem = { lista: cartao.parentElement, proximo: cartao.nextElementSibling };
        cartao.classList.add('arrastando');
        evento.dataTransfer.effectAllowed = 'move';
    });
    cartao.addEventListener('dragend', () => {
        cartao.classList.remove('arrastando');
        document.querySelectorAll('.recebendo').forEach(l => l.classList.remove('recebendo'));
        arrastado = null;
    });
});

// Descobre antes de qual cartão soltar, pela altura do mouse
function cartaoDepoisDoMouse(lista, y) {
    const outros = [...lista.querySelectorAll('.cartao:not(.arrastando)')];
    return outros.find(cartao => {
        const caixa = cartao.getBoundingClientRect();
        return y < caixa.top + caixa.height / 2;
    });
}

function atualizarContadores() {
    document.querySelectorAll('.coluna').forEach(coluna => {
        coluna.querySelector('.contador').textContent = coluna.querySelectorAll('.cartao').length;
    });
}

async function salvar(cartao, lista) {
    const ordem = [...lista.querySelectorAll('.cartao')].map(c => Number(c.dataset.id));
    try {
        const resposta = await fetch(cartao.dataset.urlMover, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': pagina.dataset.csrf },
            body: JSON.stringify({ status: lista.dataset.status, ordem }),
        });
        if (!resposta.ok) throw new Error(resposta.status);
    } catch (erro) {
        alert('Não consegui salvar a mudança. A página vai recarregar.');
        location.reload();
    }
}

document.querySelectorAll('.kanban-lista').forEach(lista => {
    lista.addEventListener('dragover', evento => {
        if (!arrastado) return;
        evento.preventDefault();  // sem isso o navegador não deixa soltar aqui
        lista.classList.add('recebendo');
        const depois = cartaoDepoisDoMouse(lista, evento.clientY);
        if (depois) {
            lista.insertBefore(arrastado, depois);
        } else {
            lista.appendChild(arrastado);
        }
    });
    lista.addEventListener('dragleave', evento => {
        if (!lista.contains(evento.relatedTarget)) lista.classList.remove('recebendo');
    });
    lista.addEventListener('drop', evento => {
        evento.preventDefault();
        lista.classList.remove('recebendo');
        if (!arrastado) return;
        // "feito" é ordenado pela data de conclusão (o mais novo em cima), não à mão:
        // quem chega de outra coluna vai para o topo; dentro de "feito", volta ao lugar.
        if (lista.dataset.status === 'feito') {
            if (origem.lista === lista) {
                lista.insertBefore(arrastado, origem.proximo);
                return;  // nada mudou
            }
            lista.prepend(arrastado);
        }
        atualizarContadores();
        salvar(arrastado, lista);
    });
});
