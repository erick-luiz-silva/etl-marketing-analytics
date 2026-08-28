# Normalização de nome_painel — aplicada na GOLD (não na Silver), para permitir
# ajustar mapeamentos sem reprocessar a extração. Mesmo princípio das keywords
# do projeto monitoramento_proposicoes.
#
# Cada entrada: (rotulo canônico, termo). 'termo' é um fragmento de regex usado
# com o operador ~* do Postgres (case-insensitive) contra silver.ga4_eventos.nome_painel_raw.
# Quando mais de um termo casa, vence o mais longo (ver gold.vw_painel_normalizado).
#
# Os primeiros itens vêm das grafias REAIS observadas no teste 3 (2026-08).
# Os demais são painéis do readme_previo ainda sem tráfego — revisar quando aparecerem.
PAINEIS = [
    # --- observados nos dados ---
    ("Cotações - CEPEA (Suínos)",        r"cepea"),
    ("Cotações - Bolsas Estaduais",      r"bolsa"),
    ("Cotações - Preços de Referência",  r"refer[êe]nc"),
    ("Cotações - Insumos",               r"insumo"),
    ("Custos de Produção",               r"custo"),
    ("Comércio Exterior",                r"com[ée]rcio exterior|comex"),
    ("IBGE Abate",                       r"ibge"),
    ("SIF Abate",                        r"sif.*abate|abate.*sif"),
    ("SIF Estabelecimentos",             r"estabelecimento"),
    ("Cenário Empresarial",              r"cen[áa]rio empresarial"),
    ("Matrizes Tecnificadas",            r"matriz"),
    ("Tutorial",                         r"^tutorial$"),
    # --- readme_previo, ainda sem tráfego ---
    ("Emprego - Perfil (RAIS)",          r"emprego.*perfil|rais"),
    ("Emprego - Movimentação (CAGED)",   r"emprego.*movim|caged"),
    ("Crédito Rural - Suinocultura",     r"cr[ée]dito.*suin"),
    ("Crédito Rural - Programas",        r"cr[ée]dito.*programa|cr[ée]dito.*recurso"),
    ("Competitividade",                  r"competit"),
    ("Mercado Global",                   r"mercado global|usda"),
]
