-- Camada gold: regras de negócio e agregações prontas para o Power BI.
--   - silver.ga4_eventos (Report A): tráfego robótico removido via trafego_valido;
--     métricas de sessão/usuário só a partir de gold.vw_sessoes (recorte
--     session_start), porque no runReport elas se repetem em cada linha de eventName.
--   - silver.ga4_paineis (Report B): normalização de nome_painel via silver.dim_painel.
--   - silver.ga4_usuarios (Report C): DAU/WAU/MAU com regra de bot sobre a janela.
--   - hosts que não são da ABCS (site = 'Outros', ver silver.fn_site) ficam de fora.

CREATE SCHEMA IF NOT EXISTS gold;

DROP VIEW IF EXISTS gold.vw_paineis_url_sem_mapa;
DROP VIEW IF EXISTS gold.vw_paineis_acessos;
DROP VIEW IF EXISTS gold.vw_usuarios_ativos;
DROP VIEW IF EXISTS gold.vw_qualidade_trafego;
DROP VIEW IF EXISTS gold.vw_site_overview;
DROP VIEW IF EXISTS gold.vw_institucional_eventos;
DROP VIEW IF EXISTS gold.vw_engajamento_dispositivo;
DROP VIEW IF EXISTS gold.vw_paineis_ranking;
DROP VIEW IF EXISTS gold.vw_paineis_sem_mapeamento;
DROP VIEW IF EXISTS gold.vw_painel_normalizado;
DROP VIEW IF EXISTS gold.vw_sessoes;

-- =====================================================================
-- Uso do site (silver.ga4_eventos)
-- =====================================================================

-- Base de sessões: uma linha por segmento, cada métrica lida do eventName certo.
-- No runReport a métrica se repete em cada linha de eventName, MAS não com o
-- mesmo valor: sessions/engaged/users são consistentes na linha session_start;
-- userEngagementDuration só acumula na linha user_engagement (é ~0 em
-- session_start / page_view / first_visit — daí o "98s para 97k sessões").
-- Por isso cada métrica sai de um FILTER no seu evento de origem.
CREATE VIEW gold.vw_sessoes AS
SELECT
    event_date, site, hostname, country, region, city, device_category,
    browser, operating_system, trafego_valido,
    SUM(sessions)         FILTER (WHERE event_name = 'session_start')    AS sessions,
    SUM(engaged_sessions) FILTER (WHERE event_name = 'session_start')    AS engaged_sessions,
    SUM(active_users)     FILTER (WHERE event_name = 'session_start')    AS active_users,
    COALESCE(SUM(user_engagement_seconds) FILTER (WHERE event_name = 'user_engagement'), 0)
                                                                        AS user_engagement_seconds
FROM silver.ga4_eventos
WHERE site <> 'Outros'
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10;

-- Visão consolidada dos dois sites.
CREATE VIEW gold.vw_site_overview AS
SELECT
    s.event_date,
    s.site,
    s.device_category,
    s.country,
    s.region,
    SUM(s.active_users)            AS usuarios,
    SUM(s.sessions)                AS sessoes,
    SUM(s.engaged_sessions)        AS sessoes_engajadas,
    SUM(s.user_engagement_seconds) AS tempo_engajamento_s
FROM gold.vw_sessoes s
WHERE s.trafego_valido
GROUP BY 1, 2, 3, 4, 5;

-- Eventos do site institucional. Só contagem de eventos + usuários; event_name
-- no grão (sem somar métrica de sessão entre eventos).
CREATE VIEW gold.vw_institucional_eventos AS
SELECT
    e.event_date,
    e.event_name,
    e.country,
    e.region,
    e.device_category,
    SUM(e.event_count)  AS eventos,
    SUM(e.active_users) AS usuarios
FROM silver.ga4_eventos e
WHERE e.site = 'Institucional'
  AND e.trafego_valido
GROUP BY 1, 2, 3, 4, 5;

-- Auditoria de qualidade: quanto tráfego foi classificado como robótico.
-- NÃO usar como métrica de negócio — serve para monitorar o filtro.
CREATE VIEW gold.vw_qualidade_trafego AS
SELECT
    s.event_date,
    s.site,
    s.country,
    s.region,
    SUM(s.sessions) FILTER (WHERE s.trafego_valido)     AS sessoes_validas,
    SUM(s.sessions) FILTER (WHERE NOT s.trafego_valido) AS sessoes_descartadas
FROM gold.vw_sessoes s
GROUP BY 1, 2, 3, 4;

-- =====================================================================
-- Painéis do Data Insights (silver.ga4_paineis)
-- =====================================================================

-- Resolve a grafia de nome_painel para o painel canônico: match exato em
-- silver.dim_painel.painel, senão via silver.dim_painel_alias. Grafia sem
-- correspondência (e ≠ '(not set)') fica com painel = NULL e aparece em
-- gold.vw_paineis_sem_mapeamento.
CREATE VIEW gold.vw_painel_normalizado AS
SELECT
    p.id_painel_evento,
    p.nome_painel_raw,
    COALESCE(d.painel, da.painel) AS painel
FROM silver.ga4_paineis p
LEFT JOIN silver.dim_painel d
    ON d.ativo AND d.painel = p.nome_painel_raw
LEFT JOIN silver.dim_painel_alias a
    ON a.alias = p.nome_painel_raw
LEFT JOIN silver.dim_painel da
    ON da.ativo AND da.painel = a.painel;

-- Aberturas de painel pela URL (Report D) — FONTE PRINCIPAL do ranking de painéis
-- desde 2026-10-06. Não depende da tag de clique do GTM.
--   aberturas    = page_views (inclui recarregar a página)
--   acessos      = pessoas que abriram o painel no dia (pessoa × painel × dia);
--                  aditivo entre dias -> "acessos na semana" = soma
--   pessoas_7d / pessoas_28d = pessoas únicas nos 7/28 dias até event_date;
--                  para um período, ler do último dia (não somar entre dias)
--   versao       = desktop | mobile | unica (versão do relatório aberta — proxy
--                  do dispositivo; 'unica' quando o painel tem um relatório só)
-- Um painel tem várias URLs (desktop/mobile, codificação); somar usuários entre
-- elas conta 2x quem abriu as duas versões no mesmo dia — raro.
CREATE VIEW gold.vw_paineis_acessos AS
SELECT
    p.event_date,
    d.painel,
    d.ordem_menu,
    d.tema,
    d.hierarquia,
    d.tipo,
    r.versao,
    SUM(p.page_views)   AS aberturas,
    SUM(p.usuarios)     AS acessos,
    SUM(p.usuarios_7d)  AS pessoas_7d,
    SUM(p.usuarios_28d) AS pessoas_28d
FROM silver.ga4_paginas p
JOIN silver.dim_painel_relatorio r ON r.alvo = p.alvo
JOIN silver.dim_painel d ON d.painel = r.painel AND d.ativo
WHERE p.site = 'Data Insights'
GROUP BY 1, 2, 3, 4, 5, 6, 7;

-- Auditoria: URLs de painel cujo alvo não está em silver.dim_painel_relatorio
-- (painel novo ou relatório republicado com ID novo -> cadastrar no seed).
CREATE VIEW gold.vw_paineis_url_sem_mapa AS
SELECT
    p.alvo,
    min(p.event_date)   AS primeira_data,
    max(p.event_date)   AS ultima_data,
    SUM(p.page_views)   AS aberturas,
    min(p.page_location) AS exemplo_url
FROM silver.ga4_paginas p
LEFT JOIN silver.dim_painel_relatorio r ON r.alvo = p.alvo
WHERE r.alvo IS NULL
  AND p.site = 'Data Insights'
  AND COALESCE(p.alvo, '') <> 'contato.php'
GROUP BY 1
ORDER BY 4 DESC;

-- Ranking de painéis pelo evento de clique (Report B). Desde 2026-10-06 serve
-- de AUDITORIA DO GTM — o ranking oficial é gold.vw_paineis_acessos. Sem filtro
-- de bot: abcsdata não tem onda robótica e a métrica é a contagem bruta de
-- acessos. Grão inclui event_name.
--
-- PRELIMINAR (ver testes/ACHADOS.md): painel_acessado e painel_clicado disparam
-- juntos em /relatorios/ → há dupla contagem entre os dois event_name. A
-- deduplicação exige registrar redirect_url como dimensão no GA4 (adiado).
-- Por ora, olhar cada event_name separado, NÃO somar os dois. Volume ainda
-- ínfimo (~120 eventos, ~30% ruído de teste no painel_acessado).
CREATE VIEW gold.vw_paineis_ranking AS
SELECT
    p.event_date,
    d.painel,
    d.ordem_menu,
    d.tema,
    d.hierarquia,
    p.event_name,
    SUM(p.event_count)                                                   AS acessos,
    SUM(p.sessions)                                                      AS sessoes,
    SUM(p.active_users)                                                  AS usuarios,
    SUM(p.engaged_sessions)                                              AS sessoes_engajadas,
    ROUND(SUM(p.user_engagement_seconds) / NULLIF(SUM(p.sessions), 0), 1) AS tempo_medio_seg
FROM silver.ga4_paineis p
JOIN gold.vw_painel_normalizado n ON n.id_painel_evento = p.id_painel_evento
JOIN silver.dim_painel d ON d.painel = n.painel AND d.tipo = 'painel'
WHERE p.site = 'Data Insights'
GROUP BY 1, 2, 3, 4, 5, 6;

-- Engajamento por dispositivo e painel (decisão de redesign mobile do readme).
CREATE VIEW gold.vw_engajamento_dispositivo AS
SELECT
    p.event_date,
    d.painel,
    d.tema,
    p.event_name,
    p.device_category,
    SUM(p.sessions)                AS sessoes,
    SUM(p.active_users)            AS usuarios,
    SUM(p.engaged_sessions)        AS sessoes_engajadas,
    SUM(p.user_engagement_seconds) AS tempo_engajamento_s
FROM silver.ga4_paineis p
JOIN gold.vw_painel_normalizado n ON n.id_painel_evento = p.id_painel_evento
JOIN silver.dim_painel d ON d.painel = n.painel AND d.tipo = 'painel'
WHERE p.site = 'Data Insights'
GROUP BY 1, 2, 3, 4, 5;

-- Auditoria: grafias de nome_painel sem correspondência em dim_painel nem
-- dim_painel_alias — cada uma precisa de apelido novo (ou é painel novo que
-- falta no seed). '(not set)' fica de fora (é problema de GTM, não de mapa).
CREATE VIEW gold.vw_paineis_sem_mapeamento AS
SELECT
    n.nome_painel_raw,
    SUM(p.event_count) AS eventos
FROM gold.vw_painel_normalizado n
JOIN silver.ga4_paineis p ON p.id_painel_evento = n.id_painel_evento
WHERE n.painel IS NULL
  AND n.nome_painel_raw <> '(not set)'
  AND p.site = 'Data Insights'
GROUP BY 1
ORDER BY 2 DESC;

-- =====================================================================
-- Usuários ativos (silver.ga4_usuarios)
-- =====================================================================

-- DAU / WAU / MAU de tráfego válido, por dia × site × país × dispositivo.
-- dau/wau/mau = usuários únicos dos últimos 1/7/28 dias terminando em event_date
-- (MAU = 28 dias móveis, padrão GA4; wau no domingo = WAU seg–dom fechado).
-- Somar entre país/dispositivo infla ~2% (usuário que troca de linha na janela);
-- somar entre DIAS é errado — para um período, ler o valor do último dia.
--
-- Regra de bot = mesma da silver (engajou E não é blob >= 30 sessões com < 5%
-- de engajamento), mas aplicada às sessões da JANELA de cada métrica: um
-- segmento entra no wau se suas sessões dos últimos 7 dias passam na regra.
--
-- Sessões/engajamento/tempo saem no mesmo recorte dos usuários, para as razões
-- (visitas por usuário etc.) fecharem:
--   sessoes, sessoes_engajadas, tempo_engajamento_s -> do dia, regra do dau
--                                                      (aditivas entre dias)
--   *_7d -> soma dos 7 dias até event_date, regra do wau (no domingo = semana
--           seg–dom no mesmo recorte do wau; NÃO somar entre dias)
CREATE VIEW gold.vw_usuarios_ativos AS
WITH janelas AS (
    SELECT
        event_date, site, hostname, country, device_category, dau, wau, mau,
        sessions                AS ses_1d,
        engaged_sessions        AS eng_1d,
        user_engagement_seconds AS tempo_1d,
        SUM(sessions) OVER w7                AS ses_7d,
        SUM(engaged_sessions) OVER w7        AS eng_7d,
        SUM(user_engagement_seconds) OVER w7 AS tempo_7d,
        SUM(sessions) OVER w28               AS ses_28d,
        SUM(engaged_sessions) OVER w28       AS eng_28d
    FROM silver.ga4_usuarios
    WHERE site <> 'Outros'
    WINDOW
        w7  AS (PARTITION BY hostname, country, device_category ORDER BY event_date
                RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW),
        w28 AS (PARTITION BY hostname, country, device_category ORDER BY event_date
                RANGE BETWEEN INTERVAL '27 days' PRECEDING AND CURRENT ROW)
),
flags AS (
    SELECT *,
        eng_1d  > 0 AND NOT (ses_1d  >= 30 AND eng_1d::numeric  / ses_1d  < 0.05) AS valido_1d,
        eng_7d  > 0 AND NOT (ses_7d  >= 30 AND eng_7d::numeric  / ses_7d  < 0.05) AS valido_7d,
        eng_28d > 0 AND NOT (ses_28d >= 30 AND eng_28d::numeric / ses_28d < 0.05) AS valido_28d
    FROM janelas
)
SELECT
    event_date,
    site,
    country,
    device_category,
    SUM(dau)      FILTER (WHERE valido_1d)  AS dau,
    SUM(wau)      FILTER (WHERE valido_7d)  AS wau,
    SUM(mau)      FILTER (WHERE valido_28d) AS mau,
    SUM(ses_1d)   FILTER (WHERE valido_1d)  AS sessoes,
    SUM(eng_1d)   FILTER (WHERE valido_1d)  AS sessoes_engajadas,
    SUM(tempo_1d) FILTER (WHERE valido_1d)  AS tempo_engajamento_s,
    SUM(ses_7d)   FILTER (WHERE valido_7d)  AS sessoes_7d,
    SUM(eng_7d)   FILTER (WHERE valido_7d)  AS sessoes_engajadas_7d,
    SUM(tempo_7d) FILTER (WHERE valido_7d)  AS tempo_engajamento_7d_s
FROM flags
GROUP BY 1, 2, 3, 4;
