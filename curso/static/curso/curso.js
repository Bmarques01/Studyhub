// Clicar numa disciplina da grade abre a janela (<dialog>) já preenchida com os dados dela.
const dialogo = document.getElementById('dialogo-situacao');
const form = document.getElementById('form-situacao');

function abrir(celula) {
    const d = celula.dataset;
    form.action = d.url;
    // textContent: os textos entram como texto puro, nunca como código
    document.getElementById('dlg-codigo').textContent = `${d.codigo} · ${d.horas}h`;
    document.getElementById('dlg-nome').textContent = d.nome;
    document.getElementById('dlg-requisitos').textContent =
        d.requisitos ? `Pré-requisitos: ${d.requisitos}` : 'Sem pré-requisitos.';

    form.querySelector(`input[name="situacao"][value="${d.situacao}"]`).checked = true;
    form.elements.semestre_cursado.value = d.semestreCursado;
    form.elements.nota_final.value = d.nota;

    const link = document.getElementById('dlg-estudos');
    link.hidden = !d.estudos;
    if (d.estudos) link.href = d.estudos;

    dialogo.showModal();
}

document.querySelectorAll('.celula-grade').forEach(celula => {
    celula.addEventListener('click', () => abrir(celula));
});

dialogo.querySelector('[data-fechar]').addEventListener('click', () => dialogo.close());

// clicar fora da janela também fecha
dialogo.addEventListener('click', evento => {
    if (evento.target === dialogo) dialogo.close();
});

// Depois de salvar, a página volta com #d123 no endereço: destaca a disciplina alterada
if (location.hash.startsWith('#d')) {
    const alterada = document.querySelector(location.hash);
    alterada?.scrollIntoView({ block: 'center' });
}
