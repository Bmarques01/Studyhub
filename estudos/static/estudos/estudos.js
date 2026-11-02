// Modo edição por categoria: o lápis da categoria mostra todos os controles dela.
// O navegador lembra quais categorias estavam abertas (sessionStorage), para que
// a edição continue aberta depois de salvar algo (a página recarrega a cada ação).

const CHAVE = 'estudos-categorias-em-edicao';
const abertas = new Set(JSON.parse(sessionStorage.getItem(CHAVE) || '[]'));

function salvar() {
    sessionStorage.setItem(CHAVE, JSON.stringify([...abertas]));
}

function alternar(secao, ligar) {
    secao.classList.toggle('editando-categoria', ligar);
    if (ligar) {
        abertas.add(secao.dataset.categoria);
    } else {
        abertas.delete(secao.dataset.categoria);
        // fecha edições pequenas (nome de tópico, disciplina...) que tenham ficado abertas
        secao.querySelectorAll('.editavel.editando').forEach(fecharEdicao);
    }
    salvar();
}

// Ao abrir a página, reabre as categorias que estavam em edição
document.querySelectorAll('.categoria').forEach(secao => {
    if (abertas.has(secao.dataset.categoria)) secao.classList.add('editando-categoria');
});

document.addEventListener('click', evento => {
    const botao = evento.target.closest('[data-alternar-edicao]');
    if (!botao) return;
    const secao = botao.closest('.categoria');
    const ligar = !secao.classList.contains('editando-categoria');
    alternar(secao, ligar);
    if (ligar) secao.querySelector('.categoria-editar input[name="nome"]').focus();
});
