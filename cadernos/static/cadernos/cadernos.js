// Editor do caderno (Quill) com salvamento automático.
// O conteúdo vai para o Django no formato do Quill ("Delta"), nunca como HTML.

const area = document.querySelector('.caderno-pagina');
const elEditor = document.getElementById('editor');

if (area && elEditor) {
    const destaque = getComputedStyle(area).getPropertyValue('--destaque').trim();
    // Marca-texto: a cor do caderno + alguns tons pastel. "false" = tirar o marca-texto.
    const MARCA_TEXTO = [destaque, '#fff3a3', '#c8f2d4', '#cfe3ff', '#ffd6e7', '#e8dcff', false];

    const quill = new Quill(elEditor, {
        theme: 'snow',
        placeholder: elEditor.dataset.placeholder || 'Comece a escrever...',
        modules: {
            toolbar: [
                [{ header: [1, 2, 3, false] }],
                ['bold', 'italic', 'underline', 'strike'],
                [{ background: MARCA_TEXTO }],
                [{ list: 'ordered' }, { list: 'bullet' }, { list: 'check' }],
                ['blockquote', 'code-block', 'link'],
                ['clean'],
            ],
        },
    });

    // Conteúdo salvo, enviado pelo Django de forma segura (json_script)
    const salvo = JSON.parse(document.getElementById('conteudo-pagina').textContent);
    if (salvo && Array.isArray(salvo.ops)) quill.setContents(salvo, 'silent');

    const campoTitulo = document.getElementById('titulo-pagina');
    const campoTopico = document.getElementById('topico-pagina');
    const status = document.getElementById('status-salvo');
    const tituloNaLista = document.querySelector(`.lista-paginas a[data-pagina="${area.dataset.pagina}"] .titulo-na-lista`);

    let espera = null;
    let pendente = false;

    function mostrar(texto, classe = '') {
        status.textContent = texto;
        status.className = `status-salvo ${classe}`;
    }

    function dados(extra = {}) {
        return JSON.stringify({
            titulo: campoTitulo.value,
            conteudo: quill.getContents(),
            texto: quill.getText(),
            ...extra,
        });
    }

    async function salvar(extra = {}) {
        clearTimeout(espera);
        pendente = false;
        mostrar('salvando...', 'salvando');
        try {
            const resposta = await fetch(area.dataset.urlSalvar, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': area.dataset.csrf },
                body: dados(extra),
            });
            const json = await resposta.json();
            if (!resposta.ok) throw new Error(json.erro || resposta.status);
            mostrar(`salvo às ${json.salvo_em} ✓`);
            if (tituloNaLista) tituloNaLista.textContent = campoTitulo.value || 'Sem título';
        } catch (erro) {
            mostrar(`não salvou (${erro.message}) · tentando de novo`, 'erro');
            pendente = true;
            espera = setTimeout(salvar, 5000);
        }
    }

    // Espera você parar de digitar por ~1 segundo antes de salvar
    function agendar() {
        pendente = true;
        mostrar('editando...', 'salvando');
        clearTimeout(espera);
        espera = setTimeout(salvar, 900);
    }

    quill.on('text-change', (_mudanca, _antes, origem) => {
        if (origem === 'user') agendar();
    });
    campoTitulo.addEventListener('input', agendar);
    campoTitulo.addEventListener('keydown', evento => {
        if (evento.key === 'Enter') {  // Enter no título pula para o texto
            evento.preventDefault();
            quill.focus();
        }
    });
    campoTopico?.addEventListener('change', () => salvar({ topico_id: campoTopico.value }));

    // Se fechar a aba com algo por salvar, manda mesmo assim (keepalive)
    window.addEventListener('beforeunload', () => {
        if (!pendente) return;
        fetch(area.dataset.urlSalvar, {
            method: 'POST',
            keepalive: true,
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': area.dataset.csrf },
            body: dados(),
        });
    });

    // Página nova: já começa com o cursor no título
    if (!quill.getText().trim() && /^(Nova página|Primeira página|Sem título)$/.test(campoTitulo.value)) {
        campoTitulo.select();
    }
}

// Janela "+ material": colar o HTML ou enviar o arquivo
const dialogoMaterial = document.getElementById('dialogo-material');
if (dialogoMaterial) {
    document.querySelectorAll('[data-abrir-material]').forEach(botao => botao.addEventListener('click', () => {
        dialogoMaterial.showModal();
        dialogoMaterial.querySelector('textarea').focus();
    }));
    dialogoMaterial.querySelector('[data-fechar]').addEventListener('click', () => dialogoMaterial.close());
}

// Material: o guia (na caixa isolada) avisa quando guarda algo, ex.: uma aula marcada como estudada.
// Só aceitamos mensagens vindas do próprio iframe do material.
const quadroMaterial = document.querySelector('.material-frame');
if (quadroMaterial && area) {
    let esperaArmazenamento = null;
    window.addEventListener('message', evento => {
        if (evento.source !== quadroMaterial.contentWindow || evento.data?.studyhub !== 'armazenamento') return;
        clearTimeout(esperaArmazenamento);
        esperaArmazenamento = setTimeout(() => {
            fetch(area.dataset.urlSalvar, {
                method: 'POST',
                keepalive: true,
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': area.dataset.csrf },
                body: JSON.stringify({ armazenamento: evento.data.dados }),
            });
        }, 400);
    });
}
