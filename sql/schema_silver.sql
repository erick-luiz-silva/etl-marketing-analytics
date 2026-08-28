-- Camada silver: dados achatados e normalizados, SEM regra de negócio.
-- Preserva TODAS as linhas (inclusive tráfego robótico) para auditoria — a
-- única classificação aqui é a coluna trafego_valido, um flag de qualidade
-- transparente e ajustável. A remoção de bot acontece na gold (WHERE trafego_valido).
--
-- Por que não filtrar bot aqui como no readme_previo: a GA4 Data API não tem a
-- dimensão sessionEngaged (só o export BigQuery), e os bots atuais usam
-- browser='Chrome'/OS='Windows' — o filtro por browser vazio não pega nada.
-- Sinal robótico confiável no grão agregado: engaged_sessions = 0
-- (a onda de bots da China tem 0 sessões engajadas; algumas linhas de
-- user_engagement ainda trazem tempo residual > 0, então o tempo sozinho
-- não serve de filtro — ver testes/ACHADOS.md, teste 4).

CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.ga4_eventos (
    id_evento               BIGSERIAL PRIMARY KEY,
    event_date              DATE NOT NULL,
    hostname                VARCHAR(120) NOT NULL,
    site                    VARCHAR(20)  NOT NULL,   -- 'Data Insights' | 'Institucional'
    country                 VARCHAR(100) NOT NULL,
    city                    VARCHAR(120) NOT NULL,
    device_category         VARCHAR(20)  NOT NULL,
    browser                 VARCHAR(60)  NOT NULL,
    operating_system        VARCHAR(60)  NOT NULL,
    event_name              VARCHAR(80)  NOT NULL,
    nome_painel_raw         VARCHAR(200) NOT NULL,   -- grafia crua; '(not set)' quando ausente
    event_count             BIGINT,
    sessions                BIGINT,
    engaged_sessions        BIGINT,
    active_users            BIGINT,
    user_engagement_seconds NUMERIC(14,2),
    trafego_valido          BOOLEAN NOT NULL,        -- engaged_sessions > 0
    data_extracao           TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_silver_ga4_eventos_event_date
    ON silver.ga4_eventos (event_date);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_eventos_site
    ON silver.ga4_eventos (site);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_eventos_event_name
    ON silver.ga4_eventos (event_name);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_eventos_valido
    ON silver.ga4_eventos (trafego_valido);

-- Tabela de configuração: mapeamento de grafias de nome_painel -> nome canônico.
-- 'termo' é fragmento de regex (~*) aplicado sobre nome_painel_raw na gold.
-- Populada por src/load_dimensoes.py a partir de src/paineis.py.
CREATE TABLE IF NOT EXISTS silver.dim_painel (
    id_painel SERIAL PRIMARY KEY,
    termo     VARCHAR(120) UNIQUE NOT NULL,
    rotulo    VARCHAR(120) NOT NULL,
    ativo     BOOLEAN NOT NULL DEFAULT true
);
