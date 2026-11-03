// Página dos flashcards: ao escolher a disciplina, a lista de tópicos mostra só os dela.
const topicosPorDisciplina = JSON.parse(document.getElementById('topicos-por-disciplina').textContent);

function atualizarTopicos(form) {
    const disciplina = form.querySelector('select[name="disciplina"]').value;
    const select = form.querySelector('select[name="topico"]');
    select.replaceChildren(new Option('sem tópico', ''));
    for (const [id, nome] of topicosPorDisciplina[disciplina] || []) {
        select.add(new Option(nome, id));  // new Option usa texto puro (não vira HTML)
    }
    select.disabled = select.options.length === 1;
}

document.querySelectorAll('form[data-topicos]').forEach(form => {
    form.querySelector('select[name="disciplina"]').addEventListener('change', () => atualizarTopicos(form));
    atualizarTopicos(form);  // a disciplina pode já vir escolhida pelo filtro
});
