// Tela "gerar com IA": mostra/esconde as opções e avisa enquanto o Claude trabalha.

// Desmarcou "questões" ou "flashcards": as opções daquela parte ficam apagadas
document.querySelectorAll('[data-liga]').forEach(caixa => {
    const detalhes = document.querySelector(`[data-detalhes="${caixa.dataset.liga}"]`);
    const atualizar = () => detalhes.classList.toggle('desligado', !caixa.checked);
    caixa.addEventListener('change', atualizar);
    atualizar();
});

// Ao enviar: trava o botão (cada clique é uma geração paga) e mostra que está gerando
const formGerar = document.querySelector('[data-gerar]');
formGerar?.addEventListener('submit', () => {
    const botao = formGerar.querySelector('[data-botao-gerar]');
    botao.disabled = true;
    botao.textContent = 'gerando…';
    formGerar.querySelector('[data-espera]').hidden = false;
});

// Voltou para esta página pelo "voltar" do navegador: destrava o botão
window.addEventListener('pageshow', evento => {
    if (!evento.persisted || !formGerar) return;
    const botao = formGerar.querySelector('[data-botao-gerar]');
    botao.disabled = false;
    botao.textContent = '✦ gerar';
    formGerar.querySelector('[data-espera]').hidden = true;
});
