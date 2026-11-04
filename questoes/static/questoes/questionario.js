// Questionário: atalhos de teclado.
// Alternativas: a letra (A, B, C...) ou V/F · aberta: S (acertei) / N (errei) · correção: Enter segue.

document.addEventListener('keydown', evento => {
    // escrevendo numa caixa de texto, as teclas são texto (não atalho)
    if (evento.ctrlKey || evento.metaKey || evento.altKey || evento.target.closest('textarea, input')) return;

    const seguir = document.querySelector('[data-seguir]');
    if (seguir && (evento.key === 'Enter' || evento.key === ' ')) {
        evento.preventDefault();
        seguir.click();
        return;
    }

    const botao = document.querySelector(`[data-responder] [data-tecla="${CSS.escape(evento.key.toLowerCase())}"]`);
    if (botao) {
        evento.preventDefault();
        botao.click();
    }
});

// Não deixa enviar duas vezes (clique duplo ou tecla repetida)
document.querySelectorAll('[data-responder]').forEach(form => form.addEventListener('submit', evento => {
    if (form.dataset.enviado) evento.preventDefault();
    form.dataset.enviado = '1';
}));
