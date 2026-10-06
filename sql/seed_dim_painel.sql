-- Snapshot versionado dos painéis do ABCS Data Insights.
-- Fonte: data/ABCS Data Insights - Painéis.csv (mantido pelo time, fora do git).
-- Aplicado por src/load_dimensoes.py. Idempotente.
--
-- Regras aplicadas na conversão do CSV:
--   - 'Comércio Exterior - Exportações' + '- Importações' -> 1 painel 'Comércio Exterior'
--     (o GTM rastreia como um evento só; classificação idêntica nos dois)
--   - 'SIF - Condenações' (marcado RETIRAR no CSV) -> não entra
--   - 'Tutorial' não está no CSV; entra como tipo='auxiliar' (item de navegação)
--   - 'Competitividade Carne Suína' e 'Mercado Global' não estão no CSV; entraram
--     em 2026-10-06 (já rastreados pelo site/GTM). Tema/hierarquia informados pelo
--     time; ordem_menu e público a definir.
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
    ('Competitividade Carne Suína',                NULL, 'COTAÇÕES/PREÇOS',           'Mercado e preços',         NULL,                                            'painel',   true),
    ('Mercado Global',                             NULL, 'COMÉRCIO EXTERIOR',         'Comércio Exterior',        NULL,                                            'painel',   true),
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
    ('Movimentação',          'Emprego - Movimentação'),
    -- Confirmados 2026-10-05 contra o export BigQuery (nome_painel x redirect_url).
    -- Grafias sem hífen / ordem trocada:
    ('Cotações Bolsas Estaduais',                'Cotações - Bolsas Estaduais'),
    ('Preços de Referência',                     'Cotações - Preços de Referência'),
    ('Matrizes Tecnificadas Modelo de Produção', 'Matrizes Tecnificadas - Modelo de Produção'),
    ('Estabelecimentos SIF',                     'SIF Estabelecimentos'),
    ('Cenário Empresarial Cadastros',            'Cenário Empresarial - Cadastros'),
    ('Crédito Rural Suinocultura',               'Crédito Rural - Suinocultura'),
    ('Comércio Exterior Importações',            'Comércio Exterior'),   -- exp + imp = 1 painel
    -- Nomes do MAPA da variável GTM "JS - Nome Painel" (versão 10, 2026-10-05):
    ('Comércio Exterior - Exportações',          'Comércio Exterior'),
    ('Comércio Exterior - Importações',          'Comércio Exterior'),
    -- Rótulo-folha (mesmo padrão de Perfil/Movimentação):
    ('Suinocultura',                             'Crédito Rural - Suinocultura'),
    ('Programas e Recursos',                     'Crédito Rural - Programas e Recursos'),
    -- Site traduzido pelo navegador (es/fr):
    ('Precios de los cerdos CEPEA',                  'Cotações Suínos - CEPEA'),
    ('Precios del cerdo - CEPEA',                    'Cotações Suínos - CEPEA'),
    ('Cotizaciones - Bolsas de Valores Estatales',   'Cotações - Bolsas Estaduais'),
    ('Cotizaciones - Precios de referencia',         'Cotações - Preços de Referência'),
    ('Precios de referencia',                        'Cotações - Preços de Referência'),
    ('Cotizaciones - Suministros',                   'Cotações - Insumos'),
    ('Cotizaciones de entrada',                      'Cotações - Insumos'),
    ('Costos de producción',                         'Custos de Produção'),
    ('Matrices tecnificadas - Modelo de producción', 'Matrizes Tecnificadas - Modelo de Produção'),
    ('Évolution du paysage commercial',              'Cenário Empresarial - Evolução'),
    ('猪肉竞争力',                                    'Competitividade Carne Suína')   -- tradução zh
ON CONFLICT (alias) DO UPDATE SET painel = EXCLUDED.painel;

-- Deliberadamente NÃO mapeado: 'Fale com a ABCS' (item de contato, não é painel).
-- Segue aparecendo em gold.vw_paineis_sem_mapeamento — ok, é sinal de auditoria.
-- Sem painel identificável (2026-10-05): 'Redução SIF' (redirect_url ambíguo).

-- Alvo do ?redirect= (ID do relatório Power BI, campo "k" do r=) -> painel.
-- Fonte das contagens oficiais de painel (gold.vw_paineis_acessos). ID novo
-- aparece em gold.vw_paineis_url_sem_mapa -> cadastrar aqui.
INSERT INTO silver.dim_painel_relatorio (alvo, painel, versao, fonte) VALUES
    -- Mapa da variável GTM "JS - Nome Painel" (versão 10, 2026-10-05). versao pelo
    -- device.category das aberturas no export (27/08–05/10): mobile/desktop >= 80%.
    ('0cf2dce7-1107-4ff6-bbba-d208ffd06164',  'Cotações - Preços de Referência',             'desktop', 'gtm'),
    ('871623e5-fc9c-45c5-999d-c22f9c4627be',  'Cotações - Preços de Referência',             'mobile',  'gtm'),
    ('145d4c18-1710-4735-b2bc-616b2d3dd750',  'Custos de Produção',                          'desktop', 'gtm'),
    ('7cb43ec0-0d90-428b-ad77-5886280959cf',  'Custos de Produção',                          'mobile',  'gtm'),
    ('1f0d25a6-7063-4aef-b5d0-d4e333b4eebf',  'SIF Estabelecimentos',                        'unica',   'gtm'),
    ('2838d21b-86ed-4dd0-ac41-8b79c2c475cd',  'Competitividade Carne Suína',                 'desktop', 'gtm'),
    ('cf338aaf-14bd-489b-9a41-807afe77dec4',  'Competitividade Carne Suína',                 'mobile',  'gtm'),
    ('2c89d796-b651-4b78-b3f7-ac184785ca0d',  'Cotações Suínos - CEPEA',                     'desktop', 'gtm'),
    ('f18fbc07-cbb3-453f-a188-eacbb3a0a4e2',  'Cotações Suínos - CEPEA',                     'mobile',  'gtm'),
    ('2ecb122b-025d-4d1b-b1fd-af109ea5fdc9',  'Crédito Rural - Suinocultura',                'unica',   'gtm'),
    ('faac1797-ff36-4ae8-8959-ba91f5a3cae2',  'Crédito Rural - Programas e Recursos',        'unica',   'gtm'),
    ('2f84f0dd-a039-46d1-80ba-471808188eb6',  'Comércio Exterior',                           'desktop', 'gtm'),  -- exportações
    ('5d638192-523c-420b-b75b-d18f527d5c3b',  'Comércio Exterior',                           'mobile',  'gtm'),  -- exportações
    ('69389e53-1b6b-4a7c-adfa-6d3c2d9e2a37',  'Comércio Exterior',                           'desktop', 'gtm'),  -- importações
    ('78f71132-05b0-4fdb-a10e-d66bb6ed846b',  'Comércio Exterior',                           'mobile',  'gtm'),  -- importações
    ('3add12d1-6d15-4962-b98e-ade1cedb2173',  'Cotações - Bolsas Estaduais',                 'desktop', 'gtm'),
    ('fd60c386-8cb3-49d6-aedd-2c3113b5418d',  'Cotações - Bolsas Estaduais',                 'mobile',  'gtm'),
    ('4c8f9c2b-5486-4958-aaf6-be078c04e1ef',  'Cotações - Insumos',                          'mobile',  'gtm'),
    ('dfa7b2e5-1ba3-40e6-9996-af185f25e177',  'Cotações - Insumos',                          'desktop', 'gtm'),
    ('5066e261-8cf5-417d-8775-046859345346',  'Emprego - Movimentação',                      'unica',   'gtm'),
    ('f0795c90-fba6-4080-8350-abb760cbd705',  'Emprego - Perfil',                            'unica',   'gtm'),
    ('6c313865-260d-4de0-8bba-1bde3db28edd',  'SIF Abate',                                   'mobile',  'gtm'),
    ('77672457-5993-4a09-8b2a-bebb9cb00366',  'SIF Abate',                                   'desktop', 'gtm'),
    ('d30aa021-ecc9-4c7f-a112-273f5e2d65fd',  'SIF Abate',                                   'desktop', 'gtm'),
    ('6fa6b559-3653-40ca-9e23-4cb95b9dee3f',  'Matrizes Tecnificadas - Modelo de Produção',  'desktop', 'gtm'),
    ('c72ac6fa-6c6b-44d0-8bcf-7d8466ee934d',  'Matrizes Tecnificadas - Modelo de Produção',  'mobile',  'gtm'),
    ('8350cc37-cbf9-4df6-a5c1-29e1a7af6de5',  'Mercado Global',                              'mobile',  'gtm'),
    ('cc158b2c-6a96-42c9-8f0b-09784843061f',  'Mercado Global',                              'desktop', 'gtm'),
    ('8e05cb85-77a1-40cb-8d64-8fcb7639d073',  'IBGE Abate',                                  'desktop', 'gtm'),
    ('e6d56813-3137-4e6b-8bf6-c2d06a15147a',  'IBGE Abate',                                  'mobile',  'gtm'),
    ('9217bafb-0786-43f4-b88a-9e8afcfaa75d',  'Cenário Empresarial',                         'unica',   'gtm'),
    ('eb236fce-ab93-40cc-839c-2eb2584e51a2',  'Cenário Empresarial - Evolução',              'unica',   'gtm'),
    ('f1aa9f76-a584-4b28-86ba-b4fab1ac615e',  'Cenário Empresarial - Cadastros',             'unica',   'gtm'),
    -- IDs antigos (até ~meados de set/2026), fora do mapa do GTM. Inferidos em
    -- 2026-10-06 casando o page_view com o painel_acessado do mesmo usuário nos
    -- 20 s anteriores (export BigQuery); painel dominante em todos.
    ('054f7949-07fb-4566-abca-df548e12540b',  'Matrizes Tecnificadas - Modelo de Produção',  'unica',   'inferido'),
    ('1e89e34d-055c-43a9-a5d9-66c26c063260',  'Cotações Suínos - CEPEA',                     'unica',   'inferido'),
    ('54c124d3-39b5-4de7-8209-0415c9ba4549',  'Cotações - Bolsas Estaduais',                 'unica',   'inferido'),
    ('554daf31-bf45-4bb3-93dd-1ca51786290d',  'Cotações - Preços de Referência',             'unica',   'inferido'),
    ('75c060af-a754-4bfe-a9f6-17786a859b20',  'Cotações - Insumos',                          'unica',   'inferido'),
    ('7ee99348-3fec-4258-bb5c-8a544c8221b2',  'Comércio Exterior',                           'unica',   'inferido'),
    ('c437a0c3-639a-4434-8f16-ecc294e89388',  'IBGE Abate',                                  'unica',   'inferido'),
    ('e73d8faa-52f1-423a-9992-5dc1f57095d6',  'Custos de Produção',                          'unica',   'inferido'),
    -- Páginas do próprio site abertas pelo mesmo mecanismo.
    ('tutorial.php',                          'Tutorial',                                    'unica',   'site')
ON CONFLICT (alvo) DO UPDATE SET painel = EXCLUDED.painel, versao = EXCLUDED.versao,
                                  fonte = EXCLUDED.fonte;

-- Deliberadamente NÃO mapeados (aparecem ou são filtrados na auditoria):
--   'contato.php' (Fale com a ABCS — filtrado em gold.vw_paineis_url_sem_mapa);
--   '90c3897a-51fd-4dd6-a204-9548da163767' (13 aberturas em jun/2026, antes do
--   export BigQuery — sem como identificar).
