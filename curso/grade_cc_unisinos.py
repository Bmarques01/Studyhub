"""Grade curricular de Ciência da Computação - Bacharelado, Unisinos (matriz 005, 2026/2).

Usada pelo comando:  python manage.py importar_grade
Cada disciplina: (código, nome, carga horária, semestre, bloco, [pré-requisitos])
"""

GRADE = {
    'nome': 'Ciência da Computação - Bacharelado',
    'instituicao': 'Unisinos',
    'horas_optativas': 160,      # 2 optativas de 80h
    'horas_transversais': 160,   # 4 transversais de 40h
    'horas_complementares': 100,
}

O, OP, T = 'obrigatoria', 'optativa', 'transversal'

DISCIPLINAS = [
    # 1º semestre
    ('001010', 'Desenvolvimento Pessoal e Profissional', 40, 1, O, []),
    ('062123', 'Algoritmos e Programação: Fundamentos', 80, 1, O, []),
    ('062136', 'Computação: Conceitos e Tendências da Profissão', 80, 1, O, []),
    ('062137', 'Raciocínio Lógico', 80, 1, O, []),
    ('062138', 'Matemática para Computação', 80, 1, O, []),
    # 2º semestre
    ('061921', 'Cálculo Diferencial', 80, 2, O, []),
    ('061926', 'Álgebra Linear e Geometria Analítica', 80, 2, O, ['062123']),
    ('061939', 'Algoritmos e Programação: Orientação a Objetos', 80, 2, O, ['062123']),
    ('061945', 'Engenharia de Software: Fundamentos', 80, 2, O, []),
    ('061980', 'Sistemas Digitais', 80, 2, O, []),
    # 3º semestre
    ('061942', 'Fundamentos de Banco de Dados', 80, 3, O, ['061939']),
    ('061943', 'Algoritmos e Programação: Estruturas de Dados', 80, 3, O, ['061939']),
    ('061944', 'Organização e Arquitetura de Computadores', 80, 3, O, ['061980']),
    ('061946', 'Paradigmas de Programação', 40, 3, O, ['061939']),
    ('061952', 'Engenharia de Software: Arquitetura e Padrões', 80, 3, O, ['061945']),
    # 4º semestre
    ('061932', 'Cálculo Integral e de Várias Variáveis', 80, 4, O, ['061921']),
    ('061947', 'Sistemas Operacionais: Fundamentos', 80, 4, O, ['061939']),
    ('061948', 'Redes de Computadores: Aplicação e Transporte', 80, 4, O, ['061939']),
    ('061949', 'Análise e Projeto de Algoritmos', 80, 4, O, ['061939']),
    ('061950', 'Linguagens Formais e Autômatos', 80, 4, O, ['061939']),
    # 5º semestre
    ('061941', 'Design de Interação Humano-Computador', 80, 5, O, []),
    ('061951', 'Algoritmos e Programação: Estruturas Avançadas de Dados', 80, 5, O, ['061943']),
    ('061953', 'Inteligência Artificial e Aprendizado de Máquina', 80, 5, O, ['061943']),
    ('061954', 'Sistemas de Gerência de Banco de Dados', 40, 5, O, ['061942']),
    ('061955', 'Sistemas Operacionais: Análise e Aplicações', 40, 5, O, ['061947']),
    # 6º semestre
    ('061956', 'Redes de Computadores: Internetworking, Roteamento e Transmissão', 80, 6, O, ['061948']),
    ('061957', 'Processamento Gráfico: Fundamentos', 80, 6, O, ['061943']),
    ('061958', 'Teoria da Computação', 80, 6, O, ['061950']),
    ('061959', 'Ciência de Dados e Big Data', 40, 6, O, ['061942']),
    ('061960', 'Controle Estatístico da Qualidade', 40, 6, O, []),
    # 7º semestre
    ('061961', 'Teoria da Informação: Compressão e Criptografia', 80, 7, O, ['061951']),
    ('061962', 'Processamento Gráfico: Computação Gráfica e Aplicações', 80, 7, O, ['061957']),
    ('061963', 'Computação de Alto Desempenho', 80, 7, O, ['061948']),
    ('061964', 'Laboratório de Inteligência Artificial', 40, 7, O, ['061953']),
    ('061965', 'Projeto Aplicado 1', 80, 7, O, []),
    # 8º semestre
    ('061966', 'Simulação e Modelagem de Sistemas', 80, 8, O, ['061951']),
    ('061967', 'Compiladores', 80, 8, O, ['061950']),
    ('061968', 'Sistemas Distribuídos', 80, 8, O, ['061948']),
    ('061969', 'Internet das Coisas: Sensores, Protocolos e Aplicações', 40, 8, O, ['061951']),
    ('061970', 'Projeto Aplicado 2', 80, 8, O, ['061965']),

    # Optativas (5º período): escolher até completar 160h.
    # As vagas genéricas "Optativa" (001001/001002) não entram: valem as disciplinas escolhidas.
    ('001011', 'Cultura Surda e LIBRAS', 80, None, OP, []),
    ('001012', 'Inclusão e Acessibilidade em Contextos Profissionais', 80, None, OP, []),
    ('001048', 'Design thinking and problem solving: Multi-Institute COIL', 80, None, OP, []),
    ('011152', '400 anos das Missões Jesuítico-Guarani no Rio Grande do Sul: Viagem de Estudos', 40, None, OP, []),
    ('061971', 'Tópicos Avançados em Ciência da Computação', 80, None, OP, []),
    ('061973', 'Circuitos Microprocessados', 80, None, OP, []),
    ('061974', 'Realidade Virtual', 80, None, OP, []),
    ('061975', 'Desenvolvimento para Web', 80, None, OP, []),
    ('061976', 'Redes Avançadas', 40, None, OP, []),
    ('061982', 'Modelagem 3D e Desenho Técnico', 80, None, OP, []),
    ('062387', 'Special Topics in Computing: Trending Information Technologies', 80, None, OP, []),
    ('062388', 'Tópicos Especiais em Computação: Aprendizado por Reforço', 80, None, OP, []),
    ('062389', 'Tópicos Especiais em Computação: Introdução à Computação Quântica', 80, None, OP, []),
    ('062560', 'Tópicos Especiais em Computação: Computação Aplicada ao Futebol', 80, None, OP, []),
    ('062561', 'Tópicos Especiais em Computação: Realidade Virtual, Aumentada e Mista', 80, None, OP, []),
    ('062613', 'Special Topics in Computing: Applied Computing in Healthcare', 80, None, OP, []),

    # Transversais: até completar 160h. As vagas genéricas entram porque podem ser compensadas.
    ('001023', 'Optativa - Transversal', 40, None, T, []),
    ('001024', 'Optativa - Transversal', 40, None, T, []),
    ('001025', 'Optativa - Transversal', 40, None, T, []),
    ('001026', 'Optativa - Transversal', 40, None, T, []),
    ('001038', 'Afrodescendentes, Povos Indígenas e Antirracismos no Brasil Contemporâneo', 40, None, T, []),
    ('001039', 'Sustentabilidade Socioambiental', 40, None, T, []),
    ('001040', 'Diversidade e Inclusão: Perspectivas Contemporâneas', 40, None, T, []),
    ('001041', 'Ética na Contemporaneidade', 40, None, T, []),
    ('001042', 'Empreendedorismo e Negócios de Impacto', 40, None, T, []),
    ('001043', 'Modelagem de Negócios de Impacto Socioambiental', 40, None, T, []),
    ('001044', 'Cidades Criativas, Inteligentes e Sustentáveis', 40, None, T, []),
    ('001045', 'Espaços Colaborativos de Transformação nas Cidades', 40, None, T, []),
    ('001046', 'Inteligência Artificial e Sociedade', 40, None, T, []),
    ('001047', 'Cultura Digital e Tecnologias Exponenciais', 40, None, T, []),
    ('001049', 'Artificial Intelligence and Society', 40, None, T, []),
    ('001050', 'Digital Culture and Exponential Technologies', 40, None, T, []),
    ('001051', 'Innovation, Entrepreneurship and Social Enterprise', 40, None, T, []),
    ('001052', 'Social Enterprise Modeling', 40, None, T, []),
    ('001053', 'Creative, Smart and Sustainable Cities through the Lenses of Innovation', 40, None, T, []),
    ('001054', 'Urban Co-Lab: Designing Together for Change', 40, None, T, []),
    ('010884', 'Viagem de Estudos - Moving the Cities', 80, None, T, []),
    ('010928', 'Solutions Lab Global', 40, None, T, []),
    ('010929', 'Socio-Environmental Sustainability', 40, None, T, []),
    ('031505', 'Gêneros de Divulgação Científica', 40, None, T, []),
    ('040359', 'Produção Textual Acadêmica', 40, None, T, []),
    ('062618', 'Moving the Cities', 80, None, T, []),
]
