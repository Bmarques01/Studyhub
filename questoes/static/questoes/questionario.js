// Questionário: atalhos de teclado.
// Alternativas: a letra (A, B, C...) ou V/F · aberta: S (acertei) / N (errei) · correção: Enter segue
// e, se errou, 1 a 4 diz o porquê (caderno de erros).

document.addEventListener('keydown', evento => {
    // escrevendo numa caixa de texto, as teclas são texto (não atalho)
    if (evento.ctrlKey || evento.metaKey || evento.altKey || evento.target.closest('textarea, input')) return;

    const seguir = document.querySelector('[data-seguir]');
    if (seguir && (evento.key === 'Enter' || evento.key === ' ')) {
        evento.preventDefault();
        seguir.click();
        return;
    }

    const tecla = CSS.escape(evento.key.toLowerCase());
    const botao = document.querySelector(`[data-responder] [data-tecla="${tecla}"], [data-motivos] [data-tecla="${tecla}"]`);
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
