-- Snapshot versionado dos painéis do ABCS Data Insights.
-- Fonte: data/ABCS Data Insights - Painéis.csv (mantido pelo time, fora do git).
-- Aplicado por src/load_dimensoes.py. Idempotente.
--
-- Regras aplicadas na conversão do CSV:
--   - 'Comércio Exterior - Exportações' + '- Importações' -> 1 painel 'Comércio Exterior'
--     (o GTM rastreia como um evento só; classificação idêntica nos dois)
--   - 'SIF - Condenações' (marcado RETIRAR no CSV) -> não entra
--   - 'Tutorial' não está no CSV; entra como tipo='auxiliar' (item de navegação)
--   - coluna 'funcao' do CSV está vazia em todas as linhas -> não modelada

-- Tudo inativo; o upsert reativa só o que está no seed (cobre painel removido do CSV).
UPDATE silver.dim_painel SET ativo = false;

INSERT INTO silver.dim_painel (painel, ordem_menu, tema, hierarquia, publico_principal, tipo, ativo) VALUES
    ('Cotações Suínos - CEPEA',                    1,  'COTAÇÕES/PREÇOS',           'Mercado e preços',         'Produtores; Associações',                        'painel',   true),
    ('Cotações - Bolsas Estaduais',                2,  'COTAÇÕES/PREÇOS',           'Mercado e preços',         'Produtores; Associações',                        'painel',   true),
    ('Cotações - Preços de Referência',            3,  'COTAÇÕES/PREÇOS',           'Mercado e preços',         'Produtores; Agroindústrias',                     'painel',   true),
    ('Cotações - Insumos',                         4,  'COTAÇÕES/PREÇOS',           'Mercado e preços',         'Produtores; Agroindústrias',                     'painel',   true),
    ('Custos de Produção',                         5,  'CUSTOS DE PRODUÇÃO',        'Produção',                 'Produtores; Associações',                        'painel',   true),
    ('Comércio Exterior',                          6,  'COMÉRCIO EXTERIOR',         'Comércio Exterior',        'Agroindústrias; Associações; Empresas',          'painel',   true),
    ('IBGE Abate',                                 7,  'ABATES',                   'Produção',                 'Associações; Frigoríficos; Empresas',            'painel',   true),
    ('SIF Abate',                                  8,  'ABATES',                   'Produção',                 'Frigoríficos; Associações',                      'painel',   true),
    ('Emprego - Perfil',                           9,  'EMPREGO',                  'Economia e financiamento', 'Associações; Empresas',                          'painel',   true),
    ('Emprego - Movimentação',                     10, 'EMPREGO',                  'Economia e financiamento', 'Associações; Empresas',                          'painel',   true),
    ('Crédito Rural - Suinocultura',               11, 'CRÉDITO RURAL',            'Economia e financiamento', 'Produtores; Associações; Instituições financeiras', 'painel', true),
    ('Crédito Rural - Programas e Recursos',       12, 'CRÉDITO RURAL',            'Economia e financiamento', 'Produtores; Associações; Instituições financeiras', 'painel', true),
    ('SIF Estabelecimentos',                       13, 'SEGURANÇA SANITÁRIA (SIF)', 'Segurança sanitária',     'Frigoríficos; Associações',                      'painel',   true),
    ('Cenário Empresarial',                        14, 'CENÁRIO EMPRESARIAL',       'Estrutura da cadeia',     'Empresas; Associações',                          'painel',   true),
    ('Cenário Empresarial - Cadastros',            15, 'CENÁRIO EMPRESARIAL',       'Estrutura da cadeia',     'Empresas; Associações',                          'painel',   true),
    ('Cenário Empresarial - Evolução',             16, 'CENÁRIO EMPRESARIAL',       'Estrutura da cadeia',     'Empresas; Associações',                          'painel',   true),
    ('Matrizes Tecnificadas - Modelo de Produção', 17, 'MODELOS DE PRODUÇÃO',       'Produção',                'Associações; Agroindústrias; Produtores',        'painel',   true),
    ('Tutorial',                                   NULL, '(navegação)',            '(navegação)',             NULL,                                            'auxiliar', true)
ON CONFLICT (painel) DO UPDATE SET
    ordem_menu        = EXCLUDED.ordem_menu,
    tema              = EXCLUDED.tema,
    hierarquia        = EXCLUDED.hierarquia,
    publico_principal = EXCLUDED.publico_principal,
    tipo              = EXCLUDED.tipo,
    ativo             = true;

-- Apelidos GA4 -> painel canônico. Grafias que o GTM manda diferente do nome
-- canônico (surgem em gold.vw_paineis_sem_mapeamento). Confirmados 2026-08-31.
INSERT INTO silver.dim_painel_alias (alias, painel) VALUES
    ('Cotações Suínos CEPEA', 'Cotações Suínos - CEPEA'),   -- sem hífen
    ('Cotações Insumos',      'Cotações - Insumos'),         -- sem hífen
    ('Perfil',                'Emprego - Perfil'),           -- GTM manda só o rótulo-folha
    ('Movimentação',          'Emprego - Movimentação')
ON CONFLICT (alias) DO UPDATE SET painel = EXCLUDED.painel;

-- Deliberadamente NÃO mapeado: 'Fale com a ABCS' (item de contato, não é painel).
-- Segue aparecendo em gold.vw_paineis_sem_mapeamento — ok, é sinal de auditoria.
