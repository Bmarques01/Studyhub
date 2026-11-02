// Clicar num dia do calendário preenche a data do formulário "novo evento".
const form = document.getElementById('form-novo');

document.querySelectorAll('.mes-dia').forEach(dia => {
    dia.addEventListener('click', evento => {
        if (evento.target.closest('.evento-chip')) return;  // clicou num evento: abre a edição

        form.querySelector('input[name="data"]').value = dia.dataset.data;

        document.querySelectorAll('.mes-dia.escolhido').forEach(d => d.classList.remove('escolhido'));
        dia.classList.add('escolhido');

        const titulo = form.querySelector('input[name="titulo"]');
        titulo.focus({ preventScroll: true });
        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
});
