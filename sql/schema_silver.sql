-- Camada silver: dados achatados e normalizados, SEM regra de negócio.
-- Preserva TODAS as linhas (inclusive tráfego robótico) para auditoria — a
-- única classificação aqui é a coluna trafego_valido, um flag de qualidade
-- transparente e ajustável. A remoção de bot acontece na gold (WHERE trafego_valido).
--
-- Por que não filtrar bot como no readme_previo: a GA4 Data API não tem a
-- dimensão sessionEngaged (só o export BigQuery), e os bots atuais usam
-- browser='Chrome'/OS='Windows' — o filtro por browser vazio não pega nada.
-- Sinal robótico confiável: segmento com muitas sessões e engajamento ~zero
-- (ver testes/ACHADOS.md, teste 4).

CREATE SCHEMA IF NOT EXISTS silver;

-- Portal a partir do hostName. A propriedade GA4 também recebe hits de hosts
-- que não são da ABCS (cópias do site, proxies, localhost de teste) -> 'Outros',
-- que a gold descarta. Tradutor do Google (abcs-org-br.translate.goog) conta
-- como o portal de origem.
CREATE OR REPLACE FUNCTION silver.fn_site(hostname TEXT) RETURNS VARCHAR(20)
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN hostname ILIKE 'abcsdata.abcs.org.br'
          OR hostname ILIKE 'abcsdata-abcs-org-br.translate.goog'       THEN 'Data Insights'
        WHEN hostname ILIKE ANY (ARRAY['abcs.org.br', 'www.abcs.org.br',
                                       'abcs-org-br.translate.goog'])  THEN 'Institucional'
        ELSE 'Outros'
    END
$$;

-- Report A — uso do site (histórico desde fev/2023).
CREATE TABLE IF NOT EXISTS silver.ga4_eventos (
    id_evento               BIGSERIAL PRIMARY KEY,
    event_date              DATE NOT NULL,
    hostname                VARCHAR(120) NOT NULL,
    site                    VARCHAR(20)  NOT NULL,   -- 'Data Insights' | 'Institucional' | 'Outros'
    country                 VARCHAR(100) NOT NULL,
    region                  VARCHAR(120) NOT NULL,   -- estado/província (GA4: "State of ...")
    city                    VARCHAR(120) NOT NULL,
    device_category         VARCHAR(20)  NOT NULL,
    browser                 VARCHAR(60)  NOT NULL,
    operating_system        VARCHAR(60)  NOT NULL,
    event_name              VARCHAR(80)  NOT NULL,
    event_count             BIGINT,
    sessions                BIGINT,
    engaged_sessions        BIGINT,
    active_users            BIGINT,
    user_engagement_seconds NUMERIC(14,2),
    trafego_valido          BOOLEAN NOT NULL,        -- decidido por segmento (ver transform)
    data_extracao           TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_eventos_event_date ON silver.ga4_eventos (event_date);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_eventos_site       ON silver.ga4_eventos (site);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_eventos_event_name ON silver.ga4_eventos (event_name);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_eventos_valido     ON silver.ga4_eventos (trafego_valido);

-- Report B — eventos de painel (painel_acessado / painel_clicado), com nome_painel.
-- Só existe a partir de ~jun/2026. Sem coluna trafego_valido: abcsdata não tem
-- onda de bots e a métrica de interesse é a contagem bruta de acessos por painel.
CREATE TABLE IF NOT EXISTS silver.ga4_paineis (
    id_painel_evento        BIGSERIAL PRIMARY KEY,
    event_date              DATE NOT NULL,
    hostname                VARCHAR(120) NOT NULL,
    site                    VARCHAR(20)  NOT NULL,
    country                 VARCHAR(100) NOT NULL,
    region                  VARCHAR(120) NOT NULL,
    city                    VARCHAR(120) NOT NULL,
    device_category         VARCHAR(20)  NOT NULL,
    event_name              VARCHAR(80)  NOT NULL,   -- painel_acessado | painel_clicado
    nome_painel_raw         VARCHAR(200) NOT NULL,   -- grafia crua; '(not set)' quando ausente
    event_count             BIGINT,
    sessions                BIGINT,
    engaged_sessions        BIGINT,
    active_users            BIGINT,
    user_engagement_seconds NUMERIC(14,2),
    data_extracao           TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_paineis_event_date ON silver.ga4_paineis (event_date);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_paineis_painel     ON silver.ga4_paineis (nome_painel_raw);

-- Report C — usuários ativos (DAU/WAU/MAU). dau/wau/mau = usuários únicos dos
-- últimos 1/7/28 dias terminando em event_date, por host × país × dispositivo.
-- Sem trafego_valido: a regra de bot depende da janela (7/28 dias) e é aplicada
-- na gold (gold.vw_usuarios_ativos) a partir de sessions/engaged_sessions diárias.
CREATE TABLE IF NOT EXISTS silver.ga4_usuarios (
    id_usuarios      BIGSERIAL PRIMARY KEY,
    event_date       DATE NOT NULL,
    hostname         VARCHAR(120) NOT NULL,
    site             VARCHAR(20)  NOT NULL,
    country          VARCHAR(100) NOT NULL,
    device_category  VARCHAR(20)  NOT NULL,
    dau              BIGINT,
    wau              BIGINT,
    mau              BIGINT,
    sessions                BIGINT,
    engaged_sessions        BIGINT,
    user_engagement_seconds NUMERIC(14,2),
    data_extracao           TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_usuarios_event_date ON silver.ga4_usuarios (event_date);

-- Dimensão descritiva dos painéis do ABCS Data Insights. Cada painel é
-- distinto (não são variações de grafia). Populada por src/load_dimensoes.py
-- a partir de sql/seed_dim_painel.sql, snapshot versionado do CSV mantido pelo
-- time (data/ABCS Data Insights - Painéis.csv, fora do git).
--   tipo = 'painel'   -> painel de dados (entra no ranking)
--   tipo = 'auxiliar' -> item de navegação (ex.: Tutorial)
CREATE TABLE IF NOT EXISTS silver.dim_painel (
    id_painel         SERIAL PRIMARY KEY,
    painel            VARCHAR(120) UNIQUE NOT NULL,
    ordem_menu        INT,
    tema              VARCHAR(80),
    hierarquia        VARCHAR(80),
    publico_principal VARCHAR(160),
    tipo              VARCHAR(20) NOT NULL DEFAULT 'painel',
    ativo             BOOLEAN NOT NULL DEFAULT true
);

-- Apelidos: grafias vindas do GA4 que não batem exatamente com dim_painel.painel.
CREATE TABLE IF NOT EXISTS silver.dim_painel_alias (
    alias  VARCHAR(200) PRIMARY KEY,
    painel VARCHAR(120) NOT NULL REFERENCES silver.dim_painel (painel)
);
