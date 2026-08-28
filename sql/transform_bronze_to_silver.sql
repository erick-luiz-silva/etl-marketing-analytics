-- bronze -> silver. Estratégia "substitui o dia inteiro": para cada data
-- presente na bronze, apaga as linhas da silver e reinsere a partir do
-- snapshot mais recente. Idempotente entre execuções.

DELETE FROM silver.ga4_eventos
WHERE event_date IN (SELECT DISTINCT event_date FROM bronze.ga4_eventos_raw);

WITH ultimo_snapshot AS (
    SELECT DISTINCT ON (event_date) event_date, payload, data_extracao
    FROM bronze.ga4_eventos_raw
    ORDER BY event_date, data_extracao DESC
),
expandido AS (
    SELECT
        (elem->>'date')::date                                          AS event_date,
        elem->>'hostName'                                              AS hostname,
        CASE WHEN elem->>'hostName' ILIKE '%abcsdata%'
             THEN 'Data Insights' ELSE 'Institucional' END             AS site,
        COALESCE(NULLIF(elem->>'country', ''), '(not set)')            AS country,
        COALESCE(NULLIF(elem->>'city', ''), '(not set)')              AS city,
        COALESCE(NULLIF(elem->>'deviceCategory', ''), '(not set)')    AS device_category,
        COALESCE(NULLIF(elem->>'browser', ''), '(not set)')          AS browser,
        COALESCE(NULLIF(elem->>'operatingSystem', ''), '(not set)')  AS operating_system,
        elem->>'eventName'                                            AS event_name,
        COALESCE(NULLIF(elem->>'customEvent:nome_painel', ''), '(not set)') AS nome_painel_raw,
        (elem->>'eventCount')::bigint                                 AS event_count,
        (elem->>'sessions')::bigint                                   AS sessions,
        (elem->>'engagedSessions')::bigint                            AS engaged_sessions,
        (elem->>'activeUsers')::bigint                                AS active_users,
        (elem->>'userEngagementDuration')::numeric                    AS user_engagement_seconds,
        s.data_extracao
    FROM ultimo_snapshot s, jsonb_array_elements(s.payload) elem
),
-- trafego_valido é uma propriedade do SEGMENTO (dia × host × geo × device ×
-- browser × OS), não da linha de evento: decidida pela linha session_start e
-- propagada a todos os eventos do segmento. Assim uma linha de user_engagement
-- de bot (que às vezes traz engaged/tempo residual) não escapa do filtro.
--
-- Regra: o segmento vale se teve sessão engajada E não é um blob de bot —
-- muitas sessões (>= 30) com taxa de engajamento quase nula (< 5%). Ex.: a
-- onda da China aparece como 1 segmento/dia com ~3.000 sessões e 3 engajadas
-- (0,09%). Segmentos pequenos com baixa taxa são preservados (podem ser
-- usuários reais navegando de leve — inclusive na Ásia). Limiares heurísticos,
-- revisar com mais histórico (ver testes/ACHADOS.md).
validade AS (
    SELECT
        event_date, hostname, country, city, device_category, browser, operating_system,
        COALESCE(
            bool_or(
                engaged_sessions > 0
                AND NOT (
                    sessions >= 30
                    AND engaged_sessions::numeric / NULLIF(sessions, 0) < 0.05
                )
            ) FILTER (WHERE event_name = 'session_start'),
            bool_or(engaged_sessions > 0)
        ) AS trafego_valido
    FROM expandido
    GROUP BY 1, 2, 3, 4, 5, 6, 7
)
INSERT INTO silver.ga4_eventos (
    event_date, hostname, site, country, city, device_category, browser,
    operating_system, event_name, nome_painel_raw, event_count, sessions,
    engaged_sessions, active_users, user_engagement_seconds, trafego_valido,
    data_extracao
)
SELECT
    x.event_date, x.hostname, x.site, x.country, x.city, x.device_category,
    x.browser, x.operating_system, x.event_name, x.nome_painel_raw, x.event_count,
    x.sessions, x.engaged_sessions, x.active_users, x.user_engagement_seconds,
    COALESCE(v.trafego_valido, x.engaged_sessions > 0),
    x.data_extracao
FROM expandido x
LEFT JOIN validade v USING
    (event_date, hostname, country, city, device_category, browser, operating_system);
