-- Camada gold: regras de negócio e agregações prontas para o Power BI.
--   - silver.ga4_eventos (Report A): tráfego robótico removido via trafego_valido;
--     métricas de sessão/usuário só a partir de gold.vw_sessoes (recorte
--     session_start), porque no runReport elas se repetem em cada linha de eventName.
--   - silver.ga4_paineis (Report B): normalização de nome_painel via silver.dim_painel.

CREATE SCHEMA IF NOT EXISTS gold;

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

-- Base de sessões: recorte onde as métricas de sessão/usuário são confiáveis
-- (uma linha por segmento, sem repetição por eventName).
CREATE VIEW gold.vw_sessoes AS
SELECT
    event_date, site, hostname, country, city, device_category,
    browser, operating_system, trafego_valido,
    sessions, engaged_sessions, active_users, user_engagement_seconds
FROM silver.ga4_eventos
WHERE event_name = 'session_start';

-- Visão consolidada dos dois sites.
CREATE VIEW gold.vw_site_overview AS
SELECT
    s.event_date,
    s.site,
    s.device_category,
    s.country,
    SUM(s.active_users)            AS usuarios,
    SUM(s.sessions)                AS sessoes,
    SUM(s.engaged_sessions)        AS sessoes_engajadas,
    SUM(s.user_engagement_seconds) AS tempo_engajamento_s
FROM gold.vw_sessoes s
WHERE s.trafego_valido
GROUP BY 1, 2, 3, 4;

-- Eventos do site institucional. Só contagem de eventos + usuários; event_name
-- no grão (sem somar métrica de sessão entre eventos).
CREATE VIEW gold.vw_institucional_eventos AS
SELECT
    e.event_date,
    e.event_name,
    e.country,
    e.device_category,
    SUM(e.event_count)  AS eventos,
    SUM(e.active_users) AS usuarios
FROM silver.ga4_eventos e
WHERE e.site = 'Institucional'
  AND e.trafego_valido
GROUP BY 1, 2, 3, 4;

-- Auditoria de qualidade: quanto tráfego foi classificado como robótico.
-- NÃO usar como métrica de negócio — serve para monitorar o filtro.
CREATE VIEW gold.vw_qualidade_trafego AS
SELECT
    s.event_date,
    s.site,
    s.country,
    SUM(s.sessions) FILTER (WHERE s.trafego_valido)     AS sessoes_validas,
    SUM(s.sessions) FILTER (WHERE NOT s.trafego_valido) AS sessoes_descartadas
FROM gold.vw_sessoes s
GROUP BY 1, 2, 3;

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

-- Ranking de painéis de dados. Sem filtro de bot: abcsdata não tem onda
-- robótica e a métrica é a contagem bruta de acessos. Grão inclui event_name.
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
GROUP BY 1
ORDER BY 2 DESC;
