// Botão claro/escuro do menu. A escolha fica no navegador (localStorage "tema").
// Quem aplica o tema ao abrir a página é a linha no <head> do base.html (assim a página não "pisca" clara).
(function () {
    const botao = document.querySelector('[data-trocar-tema]');
    if (!botao) return;
    const raiz = document.documentElement;

    function mostrar() {
        const escuro = raiz.dataset.tema === 'escuro';
        // o ícone mostra para onde vai: no escuro aparece o sol ("voltar para o claro")
        botao.querySelector('[data-icone-lua]').hidden = escuro;
        botao.querySelector('[data-icone-sol]').hidden = !escuro;
        const texto = escuro ? 'Modo claro' : 'Modo escuro';
        botao.title = texto;
        botao.setAttribute('aria-label', texto);
        botao.setAttribute('aria-pressed', String(escuro));
    }

    botao.addEventListener('click', () => {
        const escuro = raiz.dataset.tema !== 'escuro';
        if (escuro) raiz.dataset.tema = 'escuro';
        else delete raiz.dataset.tema;
        try { localStorage.setItem('tema', escuro ? 'escuro' : 'claro'); } catch (e) { /* sem localStorage: vale só nesta página */ }
        mostrar();
    });

    // Trocou em outra aba: esta acompanha
    window.addEventListener('storage', (evento) => {
        if (evento.key !== 'tema') return;
        if (evento.newValue === 'escuro') raiz.dataset.tema = 'escuro';
        else delete raiz.dataset.tema;
        mostrar();
    });

    mostrar();
})();
