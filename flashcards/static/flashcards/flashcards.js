// Flashcards: a janela "+ novo" (cartão / colar vários / baralho).
const topicosPorDisciplina = JSON.parse(document.getElementById('topicos-por-disciplina').textContent);
const dialogo = document.getElementById('dialogo-novo');

// Ao escolher a disciplina, a lista de baralhos mostra só os dela
function atualizarTopicos(form) {
    const disciplina = form.querySelector('select[name="disciplina"]').value;
    const select = form.querySelector('select[name="topico"]');
    select.replaceChildren(new Option('sem baralho', ''));
    for (const [id, nome] of topicosPorDisciplina[disciplina] || []) {
        select.add(new Option(nome, id));  // new Option usa texto puro (não vira HTML)
    }
    select.disabled = select.options.length === 1;
}

dialogo.querySelectorAll('form[data-topicos]').forEach(form => {
    form.querySelector('select[name="disciplina"]').addEventListener('change', () => atualizarTopicos(form));
    atualizarTopicos(form);
});

// Mostra só o formulário da aba escolhida
function mostrarAba(aba) {
    dialogo.querySelectorAll('[data-aba]').forEach(botao => {
        botao.setAttribute('aria-selected', botao.dataset.aba === aba);
    });
    dialogo.querySelectorAll('[data-conteudo]').forEach(form => {
        form.hidden = form.dataset.conteudo !== aba;
    });
}

dialogo.querySelectorAll('[data-aba]').forEach(botao => {
    botao.addEventListener('click', () => {
        mostrarAba(botao.dataset.aba);
        focarPrimeiroCampo();
    });
});

function focarPrimeiroCampo() {
    const form = dialogo.querySelector('[data-conteudo]:not([hidden])');
    // a disciplina, se ainda não foi escolhida; senão, o primeiro campo de texto
    const disciplina = form.querySelector('select[name="disciplina"]');
    (disciplina.value ? form.querySelector('textarea, input[type="text"]') : disciplina).focus();
}

// Botões que abrem a janela. Ex.: <button data-abrir-novo data-disciplina="3" data-topico="7">
document.querySelectorAll('[data-abrir-novo]').forEach(botao => {
    botao.addEventListener('click', () => {
        const { disciplina, topico, aba } = botao.dataset;
        dialogo.querySelectorAll('form').forEach(form => {
            if (disciplina) form.querySelector('select[name="disciplina"]').value = disciplina;
            if (form.matches('[data-topicos]')) {
                atualizarTopicos(form);
                form.querySelector('select[name="topico"]').value = topico || '';
            }
        });
        mostrarAba(aba || 'cartao');
        dialogo.showModal();
        focarPrimeiroCampo();
    });
});

dialogo.querySelectorAll('[data-fechar]').forEach(botao => botao.addEventListener('click', () => dialogo.close()));
// clicar fora da janela (no fundo escuro) também fecha
// (confere a posição: um clique na borda de dentro da janela também tem a janela como alvo)
dialogo.addEventListener('click', evento => {
    const caixa = dialogo.getBoundingClientRect();
    const fora = evento.clientX < caixa.left || evento.clientX > caixa.right
        || evento.clientY < caixa.top || evento.clientY > caixa.bottom;
    if (evento.target === dialogo && fora) dialogo.close();
});

// ===== Baralhos que abrem e fecham (página da disciplina) =====
// A página lembra quais estavam abertos (sessionStorage): criar, editar ou excluir um cartão
// recarrega a página, e o baralho em que você estava continua aberto.
(function () {
    const baralhos = document.querySelectorAll('details.fc-baralho');
    if (!baralhos.length) return;
    const chave = 'fc-abertos-' + location.pathname;
    let abertos = [];
    try { abertos = JSON.parse(sessionStorage.getItem(chave)) || []; } catch (e) { /* sem sessionStorage: começa tudo fechado */ }

    const alvo = location.hash.slice(1);  // veio de um link #baralho-ID (ex.: baralho recém-criado)
    baralhos.forEach(b => {
        if (abertos.includes(b.id) || b.id === alvo) b.open = true;
        b.addEventListener('toggle', () => {
            const ids = [...baralhos].filter(x => x.open).map(x => x.id);
            try { sessionStorage.setItem(chave, JSON.stringify(ids)); } catch (e) { /* tudo bem */ }
        });
    });
})();
