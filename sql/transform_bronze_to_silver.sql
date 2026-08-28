-- bronze -> silver. Estratégia "substitui o dia inteiro": para cada data
-- presente na bronze, apaga as linhas da silver e reinsere a partir do
-- snapshot mais recente. Idempotente entre execuções, sem depender de PK
-- composta com colunas nuláveis.

DELETE FROM silver.ga4_eventos
WHERE event_date IN (SELECT DISTINCT event_date FROM bronze.ga4_eventos_raw);

WITH ultimo_snapshot AS (
    SELECT DISTINCT ON (event_date) event_date, payload, data_extracao
    FROM bronze.ga4_eventos_raw
    ORDER BY event_date, data_extracao DESC
)
INSERT INTO silver.ga4_eventos (
    event_date, hostname, site, country, city, device_category, browser,
    operating_system, event_name, nome_painel_raw, event_count, sessions,
    engaged_sessions, active_users, user_engagement_seconds, trafego_valido,
    data_extracao
)
SELECT
    (elem->>'date')::date,
    elem->>'hostName',
    CASE WHEN elem->>'hostName' ILIKE '%abcsdata%' THEN 'Data Insights' ELSE 'Institucional' END,
    COALESCE(NULLIF(elem->>'country', ''), '(not set)'),
    COALESCE(NULLIF(elem->>'city', ''), '(not set)'),
    COALESCE(NULLIF(elem->>'deviceCategory', ''), '(not set)'),
    COALESCE(NULLIF(elem->>'browser', ''), '(not set)'),
    COALESCE(NULLIF(elem->>'operatingSystem', ''), '(not set)'),
    elem->>'eventName',
    COALESCE(NULLIF(elem->>'customEvent:nome_painel', ''), '(not set)'),
    (elem->>'eventCount')::bigint,
    (elem->>'sessions')::bigint,
    (elem->>'engagedSessions')::bigint,
    (elem->>'activeUsers')::bigint,
    (elem->>'userEngagementDuration')::numeric,
    (COALESCE((elem->>'engagedSessions')::bigint, 0) > 0),
    s.data_extracao
FROM ultimo_snapshot s, jsonb_array_elements(s.payload) elem;
