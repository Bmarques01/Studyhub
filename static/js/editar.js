// Edição direto na lista.
// Cada item ".editavel" tem um ".modo-ver" e um ".modo-edicao".
// A classe "editando" no item decide qual dos dois aparece (ver estudos.css).

function abrirEdicao(item) {
    // fecha qualquer outro item que esteja sendo editado
    document.querySelectorAll('.editavel.editando').forEach(fecharEdicao);
    item.classList.add('editando');
    const campo = item.querySelector(
        '.modo-edicao input:not([type="hidden"]):not([type="color"]), .modo-edicao textarea');
    campo.focus();
    campo.select();
}

function fecharEdicao(item) {
    item.classList.remove('editando');
    item.querySelector('.modo-edicao').reset();  // desfaz o que foi digitado
}

document.addEventListener('click', evento => {
    const botaoEditar = evento.target.closest('[data-editar]');
    if (botaoEditar) {
        abrirEdicao(botaoEditar.closest('.editavel'));
        return;
    }
    const botaoCancelar = evento.target.closest('[data-cancelar]');
    if (botaoCancelar) {
        fecharEdicao(botaoCancelar.closest('.editavel'));
    }
});

// Esc cancela a edição
document.addEventListener('keydown', evento => {
    if (evento.key !== 'Escape') return;
    const item = evento.target.closest('.editavel.editando');
    if (item) fecharEdicao(item);
});

// No tópico, sair do campo (clicar fora) também cancela
document.addEventListener('focusout', evento => {
    const item = evento.target.closest('.topico.editavel.editando');
    if (item && !item.contains(evento.relatedTarget)) fecharEdicao(item);
});
