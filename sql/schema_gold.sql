-- Camada gold: regras de negócio e agregações prontas para o Power BI.
-- Aqui é onde (a) o tráfego robótico é removido (WHERE trafego_valido) e
-- (b) nome_painel é normalizado via silver.dim_painel.

CREATE SCHEMA IF NOT EXISTS gold;

-- Resolve a grafia crua de nome_painel para o rótulo canônico. Quando mais de
-- um termo casa, vence o mais longo; se nada casa, mantém a grafia crua
-- (exceto '(not set)', que vira NULL).
CREATE OR REPLACE VIEW gold.vw_painel_normalizado AS
SELECT
    e.id_evento,
    e.nome_painel_raw,
    COALESCE(
        (
            SELECT p.rotulo
            FROM silver.dim_painel p
            WHERE p.ativo AND e.nome_painel_raw ~* p.termo
            ORDER BY length(p.termo) DESC
            LIMIT 1
        ),
        NULLIF(e.nome_painel_raw, '(not set)')
    ) AS painel
FROM silver.ga4_eventos e
WHERE e.event_name IN ('painel_acessado', 'painel_clicado');

-- Ranking de painéis (Data Insights) — só tráfego válido.
CREATE OR REPLACE VIEW gold.vw_paineis_ranking AS
SELECT
    e.event_date,
    n.painel,
    e.event_name,
    SUM(e.event_count)                                             AS acessos,
    SUM(e.sessions)                                                AS sessoes,
    SUM(e.active_users)                                            AS usuarios,
    SUM(e.engaged_sessions)                                        AS sessoes_engajadas,
    ROUND(SUM(e.user_engagement_seconds) / NULLIF(SUM(e.sessions), 0), 1) AS tempo_medio_seg
FROM silver.ga4_eventos e
JOIN gold.vw_painel_normalizado n ON n.id_evento = e.id_evento
WHERE e.trafego_valido
  AND n.painel IS NOT NULL
GROUP BY 1, 2, 3;

-- Engajamento por dispositivo (Data Insights).
CREATE OR REPLACE VIEW gold.vw_engajamento_dispositivo AS
SELECT
    e.event_date,
    n.painel,
    e.device_category,
    SUM(e.sessions)                 AS sessoes,
    SUM(e.active_users)             AS usuarios,
    SUM(e.user_engagement_seconds)  AS tempo_engajamento_s
FROM silver.ga4_eventos e
JOIN gold.vw_painel_normalizado n ON n.id_evento = e.id_evento
WHERE e.trafego_valido
  AND n.painel IS NOT NULL
GROUP BY 1, 2, 3;

-- Eventos do site institucional (páginas, scroll, engajamento).
CREATE OR REPLACE VIEW gold.vw_institucional_eventos AS
SELECT
    e.event_date,
    e.event_name,
    e.country,
    e.device_category,
    SUM(e.event_count)             AS eventos,
    SUM(e.sessions)                AS sessoes,
    SUM(e.active_users)            AS usuarios,
    SUM(e.user_engagement_seconds) AS tempo_engajamento_s
FROM silver.ga4_eventos e
WHERE e.site = 'Institucional'
  AND e.trafego_valido
GROUP BY 1, 2, 3, 4;

-- Visão consolidada dos dois sites.
CREATE OR REPLACE VIEW gold.vw_site_overview AS
SELECT
    e.event_date,
    e.site,
    e.device_category,
    e.country,
    SUM(e.active_users)            AS usuarios,
    SUM(e.sessions)                AS sessoes,
    SUM(e.engaged_sessions)        AS sessoes_engajadas,
    SUM(e.user_engagement_seconds) AS tempo_engajamento_s
FROM silver.ga4_eventos e
WHERE e.trafego_valido
GROUP BY 1, 2, 3, 4;

-- Auditoria de qualidade: quanto tráfego foi classificado como robótico.
-- NÃO usar como métrica de negócio — serve para monitorar o filtro.
CREATE OR REPLACE VIEW gold.vw_qualidade_trafego AS
SELECT
    e.event_date,
    e.site,
    e.country,
    SUM(e.sessions) FILTER (WHERE e.trafego_valido)     AS sessoes_validas,
    SUM(e.sessions) FILTER (WHERE NOT e.trafego_valido) AS sessoes_descartadas
FROM silver.ga4_eventos e
WHERE e.event_name = 'session_start'
GROUP BY 1, 2, 3;

-- Auditoria: grafias de nome_painel que não bateram em nenhum termo de
-- silver.dim_painel — usada para descobrir mapeamentos faltantes.
CREATE OR REPLACE VIEW gold.vw_paineis_sem_mapeamento AS
SELECT
    e.nome_painel_raw,
    SUM(e.event_count) AS eventos
FROM silver.ga4_eventos e
WHERE e.event_name IN ('painel_acessado', 'painel_clicado')
  AND e.nome_painel_raw <> '(not set)'
  AND NOT EXISTS (
      SELECT 1 FROM silver.dim_painel p
      WHERE p.ativo AND e.nome_painel_raw ~* p.termo
  )
GROUP BY 1
ORDER BY 2 DESC;
