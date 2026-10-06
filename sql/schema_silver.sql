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

-- Alvo do ?redirect= de uma URL de painel do Data Insights:
--   - painel Power BI: o ID do relatório (campo "k" do JSON em base64 no r=)
--   - página do site (tutorial.php, contato.php): o próprio nome do arquivo
-- A URL chega com 0, 1 ou 2 níveis de percent-encoding; base64url ou padrão.
CREATE OR REPLACE FUNCTION silver.fn_alvo_redirect(url TEXT) RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    u   TEXT := url;
    r64 TEXT;
BEGIN
    FOR i IN 1..2 LOOP  -- decodifica %25 primeiro, depois o resto
        u := replace(replace(replace(replace(replace(replace(replace(replace(
             u, '%25', '%'), '%3A', ':'), '%2F', '/'), '%3F', '?'), '%3D', '='),
             '%26', '&'), '%2B', '+'), '%2C', ',');
    END LOOP;
    r64 := substring(u FROM '[?&]r=([A-Za-z0-9+/_-]+)');
    IF r64 IS NULL THEN
        RETURN substring(u FROM 'redirect=([^&#?]+)');
    END IF;
    r64 := translate(r64, '-_', '+/');
    r64 := r64 || repeat('=', (4 - length(r64) % 4) % 4);
    RETURN convert_from(decode(r64, 'base64'), 'UTF8')::jsonb ->> 'k';
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END
$$;

-- Report D — page_views de URLs de painel (/relatorios/?redirect=), por dia × URL.
-- usuarios = pessoas que abriram a URL no dia; usuarios_7d/28d =
-- pessoas únicas nos 7/28 dias até event_date (janela móvel da GA4).
CREATE TABLE IF NOT EXISTS silver.ga4_paginas (
    id_pagina        BIGSERIAL PRIMARY KEY,
    event_date       DATE NOT NULL,
    hostname         VARCHAR(120) NOT NULL,
    site             VARCHAR(20)  NOT NULL,
    page_location    TEXT NOT NULL,
    alvo             VARCHAR(120),            -- silver.fn_alvo_redirect(page_location)
    page_views       BIGINT,
    usuarios         BIGINT,
    usuarios_7d      BIGINT,
    usuarios_28d     BIGINT,
    data_extracao    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_paginas_event_date ON silver.ga4_paginas (event_date);
CREATE INDEX IF NOT EXISTS ix_silver_ga4_paginas_alvo       ON silver.ga4_paginas (alvo);

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

-- Alvo do redirect (ID do relatório Power BI ou página do site) -> painel.
-- Um painel tem vários IDs (versão desktop e mobile; IDs antigos republicados).
-- Populada por sql/seed_dim_painel.sql. fonte: 'gtm' = mapa da variável
-- "JS - Nome Painel" do GTM; 'inferido' = casado com painel_acessado do mesmo
-- usuário no export BigQuery; 'site' = página do próprio site.
-- versao: 'desktop' | 'mobile' (o site abre um relatório por tipo de tela — é a
-- fonte do recorte por dispositivo) | 'unica' (painel com um relatório só, ou ID
-- antigo usado nas duas telas). Classificada pelo device.category do export.
CREATE TABLE IF NOT EXISTS silver.dim_painel_relatorio (
    alvo   VARCHAR(120) PRIMARY KEY,
    painel VARCHAR(120) NOT NULL REFERENCES silver.dim_painel (painel),
    versao VARCHAR(10)  NOT NULL,
    fonte  VARCHAR(20)  NOT NULL
);

-- Apelidos: grafias vindas do GA4 que não batem exatamente com dim_painel.painel.
CREATE TABLE IF NOT EXISTS silver.dim_painel_alias (
    alias  VARCHAR(200) PRIMARY KEY,
    painel VARCHAR(120) NOT NULL REFERENCES silver.dim_painel (painel)
);
