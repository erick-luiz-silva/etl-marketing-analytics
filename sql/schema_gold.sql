-- Camada gold: regras de negócio e agregações prontas para o Power BI.
-- Aqui é onde (a) o tráfego robótico é removido (WHERE trafego_valido) e
-- (b) nome_painel é normalizado via silver.dim_painel.
--
-- ATENÇÃO ao grão do runReport: as métricas de sessão/usuário (sessions,
-- engaged_sessions, active_users) SE REPETEM em cada linha de eventName.
-- Somá-las sem fixar um eventName infla o número. Por isso:
--   - métricas de sessão/usuário   -> sempre a partir de gold.vw_sessoes
--                                     (recorte event_name = 'session_start')
--   - contagem de eventos          -> SUM(event_count), agrupando por event_name

CREATE SCHEMA IF NOT EXISTS gold;

DROP VIEW IF EXISTS gold.vw_qualidade_trafego;
DROP VIEW IF EXISTS gold.vw_site_overview;
DROP VIEW IF EXISTS gold.vw_institucional_eventos;
DROP VIEW IF EXISTS gold.vw_engajamento_dispositivo;
DROP VIEW IF EXISTS gold.vw_paineis_ranking;
DROP VIEW IF EXISTS gold.vw_paineis_sem_mapeamento;
DROP VIEW IF EXISTS gold.vw_painel_normalizado;
DROP VIEW IF EXISTS gold.vw_sessoes;

-- Base de sessões: um recorte de silver onde as métricas de sessão/usuário
-- são confiáveis (uma linha por segmento, sem repetição por eventName).
CREATE VIEW gold.vw_sessoes AS
SELECT
    event_date,
    site,
    hostname,
    country,
    city,
    device_category,
    browser,
    operating_system,
    trafego_valido,
    sessions,
    engaged_sessions,
    active_users,
    user_engagement_seconds
FROM silver.ga4_eventos
WHERE event_name = 'session_start';

-- Resolve a grafia de nome_painel para o painel canônico: match exato em
-- silver.dim_painel.painel, senão via silver.dim_painel_alias. Grafia sem
-- correspondência (e ≠ '(not set)') fica com painel = NULL e aparece em
-- gold.vw_paineis_sem_mapeamento.
CREATE VIEW gold.vw_painel_normalizado AS
SELECT
    e.id_evento,
    e.nome_painel_raw,
    COALESCE(d.painel, da.painel) AS painel
FROM silver.ga4_eventos e
LEFT JOIN silver.dim_painel d
    ON d.ativo AND d.painel = e.nome_painel_raw
LEFT JOIN silver.dim_painel_alias a
    ON a.alias = e.nome_painel_raw
LEFT JOIN silver.dim_painel da
    ON da.ativo AND da.painel = a.painel
WHERE e.event_name IN ('painel_acessado', 'painel_clicado');

-- Ranking de painéis de dados (Data Insights) — só tráfego válido.
-- Grão: (data, painel, event_name) — event_name fixo no grupo, então as
-- métricas de sessão não cruzam eventos. Traz os atributos de dim_painel.
CREATE VIEW gold.vw_paineis_ranking AS
SELECT
    e.event_date,
    d.painel,
    d.ordem_menu,
    d.tema,
    d.hierarquia,
    e.event_name,
    SUM(e.event_count)                                                   AS acessos,
    SUM(e.sessions)                                                      AS sessoes,
    SUM(e.active_users)                                                  AS usuarios,
    SUM(e.engaged_sessions)                                              AS sessoes_engajadas,
    ROUND(SUM(e.user_engagement_seconds) / NULLIF(SUM(e.sessions), 0), 1) AS tempo_medio_seg
FROM silver.ga4_eventos e
JOIN gold.vw_painel_normalizado n ON n.id_evento = e.id_evento
JOIN silver.dim_painel d ON d.painel = n.painel AND d.tipo = 'painel'
WHERE e.trafego_valido
GROUP BY 1, 2, 3, 4, 5, 6;

-- Engajamento por dispositivo (Data Insights). event_name no grão para não
-- somar painel_acessado + painel_clicado da mesma sessão.
CREATE VIEW gold.vw_engajamento_dispositivo AS
SELECT
    e.event_date,
    d.painel,
    d.tema,
    e.event_name,
    e.device_category,
    SUM(e.sessions)                AS sessoes,
    SUM(e.active_users)            AS usuarios,
    SUM(e.engaged_sessions)        AS sessoes_engajadas,
    SUM(e.user_engagement_seconds) AS tempo_engajamento_s
FROM silver.ga4_eventos e
JOIN gold.vw_painel_normalizado n ON n.id_evento = e.id_evento
JOIN silver.dim_painel d ON d.painel = n.painel AND d.tipo = 'painel'
WHERE e.trafego_valido
GROUP BY 1, 2, 3, 4, 5;

-- Eventos do site institucional. Só contagem de eventos + usuários; sem
-- coluna de sessões (viria inflada). event_name está no grão.
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

-- Visão consolidada dos dois sites — a partir de vw_sessoes (grão de sessão).
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

-- Auditoria: grafias de nome_painel sem correspondência em dim_painel nem
-- dim_painel_alias — cada uma precisa de um apelido novo (ou é painel novo
-- que falta no seed). '(not set)' fica de fora (é problema de GTM, não de mapa).
CREATE VIEW gold.vw_paineis_sem_mapeamento AS
SELECT
    n.nome_painel_raw,
    SUM(e.event_count) AS eventos
FROM gold.vw_painel_normalizado n
JOIN silver.ga4_eventos e ON e.id_evento = n.id_evento
WHERE n.painel IS NULL
  AND n.nome_painel_raw <> '(not set)'
GROUP BY 1
ORDER BY 2 DESC;
