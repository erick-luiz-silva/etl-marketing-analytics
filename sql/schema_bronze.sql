-- Camada bronze: append-only. Cada extração de um dia grava uma NOVA linha
-- (nunca update/delete). A silver sempre lê o snapshot mais recente por data.
--
-- payload = array JSON com uma entrada por combinação de dimensões do runReport,
-- valores como string, exatamente como a GA4 Data API devolve (só achatado de
-- dimensionValues/metricValues para um objeto com chaves nomeadas).
--
-- Dois relatórios, duas tabelas (ver testes/ACHADOS.md):
--   ga4_site_raw    -> Report A, uso do site, histórico desde fev/2023
--   ga4_paineis_raw -> Report B, eventos de painel com nome_painel (~jun/2026+)

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.ga4_site_raw (
    id_bronze     BIGSERIAL PRIMARY KEY,
    event_date    DATE NOT NULL,
    payload       JSONB NOT NULL,
    linhas        INT NOT NULL,
    data_extracao TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_bronze_ga4_site_raw_event_date
    ON bronze.ga4_site_raw (event_date);

CREATE TABLE IF NOT EXISTS bronze.ga4_paineis_raw (
    id_bronze     BIGSERIAL PRIMARY KEY,
    event_date    DATE NOT NULL,
    payload       JSONB NOT NULL,
    linhas        INT NOT NULL,
    data_extracao TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_bronze_ga4_paineis_raw_event_date
    ON bronze.ga4_paineis_raw (event_date);

-- Controle da janela de cada carga, por relatório. O próximo run incremental
-- calcula seu data_inicio como min(hoje - N, data_fim_janela do último run - N):
-- se rodou ontem equivale a D-N fixo; se a máquina ficou dias parada, a janela
-- se alarga sozinha para cobrir o buraco.
CREATE TABLE IF NOT EXISTS bronze.controle_execucao (
    id_execucao        BIGSERIAL PRIMARY KEY,
    relatorio          VARCHAR(10) NOT NULL,   -- 'site' | 'painel'
    tipo_carga         VARCHAR(20) NOT NULL,   -- 'historico' | 'incremental'
    data_inicio_janela DATE NOT NULL,
    data_fim_janela    DATE NOT NULL,
    qtd_dias           INT,
    qtd_linhas         INT,
    executado_em       TIMESTAMP NOT NULL DEFAULT now()
);
