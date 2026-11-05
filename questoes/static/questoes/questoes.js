// Formulários das questões: tópicos da disciplina, tipo de questão, alternativas e "copiar".

// Os tópicos de cada disciplina, enviados pelo Django com json_script: { "3": [[id, nome], ...] }
const elTopicos = document.getElementById('dados-topicos');
const TOPICOS = elTopicos ? JSON.parse(elTopicos.textContent) : {};

// ===== Disciplina → lista de tópicos =====
document.querySelectorAll('[data-escolha-disciplina]').forEach(form => {
    const disciplina = form.querySelector('[data-disciplina]');
    const topico = form.querySelector('[data-topico]');
    if (!disciplina || !topico) return;

    function preencher(escolhido) {
        const itens = TOPICOS[disciplina.value] || [];
        topico.replaceChildren(new Option('sem tópico', ''));
        itens.forEach(([id, nome]) => topico.add(new Option(nome, id)));
        topico.value = itens.some(([id]) => String(id) === String(escolhido)) ? escolhido : '';
        topico.disabled = itens.length === 0;
    }
    disciplina.addEventListener('change', () => preencher(''));
    preencher(topico.dataset.inicial);
});

// ===== Tipo de questão: mostra só a parte que importa (alternativas, V/F ou resposta esperada) =====
const radiosTipo = document.querySelectorAll('[data-tipo]');
function mostrarSecao() {
    const tipo = [...radiosTipo].find(r => r.checked)?.value;
    document.querySelectorAll('[data-secao]').forEach(secao => { secao.hidden = secao.dataset.secao !== tipo; });
}
radiosTipo.forEach(r => r.addEventListener('change', mostrarSecao));
if (radiosTipo.length) mostrarSecao();

// ===== "+ alternativa": copia a última linha (até 8 alternativas: A a H) =====
const listaAlternativas = document.querySelector('[data-alternativas]');
const btnMais = document.querySelector('[data-mais-alternativa]');
if (listaAlternativas && btnMais) {
    const maximo = Number(listaAlternativas.dataset.maximo);
    const atualizarBotao = () => { btnMais.hidden = listaAlternativas.children.length >= maximo; };
    btnMais.addEventListener('click', () => {
        const linhas = listaAlternativas.children;
        const nova = linhas[linhas.length - 1].cloneNode(true);
        const posicao = linhas.length;
        const letra = String.fromCharCode(65 + posicao);
        const radio = nova.querySelector('input[type=radio]');
        radio.value = posicao;
        radio.checked = false;
        nova.querySelector('span').textContent = letra;
        const campo = nova.querySelector('input[type=text]');
        campo.value = '';
        campo.setAttribute('aria-label', `Alternativa ${letra}`);
        listaAlternativas.append(nova);
        campo.focus();
        atualizarBotao();
    });
    atualizarBotao();
}

// ===== Questionário: quantas questões os tópicos marcados somam =====
document.querySelectorAll('[data-topicos]').forEach(grupo => {
    const resumo = grupo.querySelector('[data-resumo]');
    const caixas = grupo.querySelectorAll('input[type=checkbox]');
    function atualizar() {
        const marcadas = [...caixas].filter(c => c.checked);
        const soma = marcadas.reduce((total, c) => total + Number(c.dataset.n), 0);
        resumo.textContent = marcadas.length
            ? `${soma} ${soma === 1 ? 'questão' : 'questões'} nos tópicos marcados`
            : `nenhum marcado = todos (${resumo.dataset.total})`;
    }
    caixas.forEach(c => c.addEventListener('change', atualizar));
    atualizar();  // o navegador pode lembrar as marcações ao voltar para a página
});

// ===== Enviar arquivo: mostra o nome do escolhido e deixa tirar =====
document.querySelectorAll('[data-arquivo]').forEach(caixa => {
    const input = caixa.querySelector('input[type=file]');
    const nome = caixa.querySelector('[data-arquivo-nome]');
    const limpar = caixa.querySelector('[data-arquivo-limpar]');
    function atualizar() {
        const arquivo = input.files[0];
        nome.textContent = arquivo ? arquivo.name : 'nenhum arquivo escolhido';
        nome.classList.toggle('escolhido', Boolean(arquivo));
        limpar.hidden = !arquivo;
    }
    input.addEventListener('change', atualizar);
    limpar.addEventListener('click', () => { input.value = ''; atualizar(); });
    atualizar();
});

// ===== Janelas: botão com data-abrir="id" abre; cancelar, Esc ou clicar fora fecham =====
document.querySelectorAll('[data-abrir]').forEach(botao => botao.addEventListener('click', () => {
    const dialogo = document.getElementById(botao.dataset.abrir);
    dialogo.showModal();
    dialogo.querySelector('input[type=text]')?.focus();
}));
document.querySelectorAll('dialog').forEach(dialogo => {
    dialogo.querySelectorAll('[data-fechar]').forEach(b => b.addEventListener('click', () => dialogo.close()));
    dialogo.addEventListener('click', evento => {
        // o clique no fundo escuro tem a janela como alvo, mas fica fora do retângulo dela
        const caixa = dialogo.getBoundingClientRect();
        const fora = evento.clientX < caixa.left || evento.clientX > caixa.right
            || evento.clientY < caixa.top || evento.clientY > caixa.bottom;
        if (evento.target === dialogo && fora) dialogo.close();
    });
});

// ===== Excluir: pergunta antes =====
document.querySelectorAll('form[data-confirmar]').forEach(form => form.addEventListener('submit', evento => {
    if (!confirm(form.dataset.confirmar)) evento.preventDefault();
}));

// ===== Copiar o pedido para o Claude =====
document.querySelectorAll('[data-copiar]').forEach(botao => botao.addEventListener('click', async () => {
    const campo = document.getElementById(botao.dataset.copiar);
    try {
        await navigator.clipboard.writeText(campo.value);
    } catch {
        campo.select();  // sem permissão de copiar: deixa selecionado para o Ctrl+C
        document.execCommand('copy');
    }
    const antes = botao.textContent;
    botao.textContent = 'copiado ✓';
    setTimeout(() => { botao.textContent = antes; }, 1800);
}));
