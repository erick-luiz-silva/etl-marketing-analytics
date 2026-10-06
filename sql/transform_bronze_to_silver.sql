-- bronze -> silver. Estratégia "substitui o dia inteiro": para cada data cujo
-- snapshot mais recente na bronze é mais novo que o que está na silver, apaga
-- as linhas da silver e reinsere a partir desse snapshot. Idempotente.
--
-- Só os dias pendentes são reprocessados (antes era o histórico inteiro, todo
-- dia). Para reprocessar tudo — ex.: mudou uma regra desta transformação —
-- rodar `python load_silver.py --completo`, que esvazia a silver antes.

-- =====================================================================
-- Report A -> silver.ga4_eventos
-- =====================================================================
CREATE TEMP TABLE _dias_site ON COMMIT DROP AS
SELECT b.event_date
FROM bronze.ga4_site_raw b
GROUP BY b.event_date
HAVING max(b.data_extracao) > COALESCE(
    (SELECT max(s.data_extracao) FROM silver.ga4_eventos s WHERE s.event_date = b.event_date),
    '-infinity');

DELETE FROM silver.ga4_eventos WHERE event_date IN (SELECT event_date FROM _dias_site);

WITH ultimo_snapshot AS (
    SELECT DISTINCT ON (event_date) event_date, payload, data_extracao
    FROM bronze.ga4_site_raw
    WHERE event_date IN (SELECT event_date FROM _dias_site)
    ORDER BY event_date, data_extracao DESC
),
expandido AS (
    SELECT
        (elem->>'date')::date                                         AS event_date,
        elem->>'hostName'                                             AS hostname,
        silver.fn_site(elem->>'hostName')                             AS site,
        COALESCE(NULLIF(elem->>'country', ''), '(not set)')           AS country,
        COALESCE(NULLIF(elem->>'region', ''), '(not set)')            AS region,
        COALESCE(NULLIF(elem->>'city', ''), '(not set)')             AS city,
        COALESCE(NULLIF(elem->>'deviceCategory', ''), '(not set)')   AS device_category,
        COALESCE(NULLIF(elem->>'browser', ''), '(not set)')         AS browser,
        COALESCE(NULLIF(elem->>'operatingSystem', ''), '(not set)') AS operating_system,
        elem->>'eventName'                                           AS event_name,
        (elem->>'eventCount')::bigint                                AS event_count,
        (elem->>'sessions')::bigint                                  AS sessions,
        (elem->>'engagedSessions')::bigint                           AS engaged_sessions,
        (elem->>'activeUsers')::bigint                               AS active_users,
        (elem->>'userEngagementDuration')::numeric                   AS user_engagement_seconds,
        s.data_extracao
    FROM ultimo_snapshot s, jsonb_array_elements(s.payload) elem
),
-- trafego_valido é propriedade do SEGMENTO (dia × host × geo × device × browser
-- × OS), decidida pela linha session_start e propagada aos demais eventos.
-- Regra: vale se teve sessão engajada E não é blob de bot — muitas sessões
-- (>= 30) com taxa de engajamento quase nula (< 5%). Limiares heurísticos.
validade AS (
    SELECT
        event_date, hostname, country, region, city, device_category, browser, operating_system,
        COALESCE(
            bool_or(
                engaged_sessions > 0
                AND NOT (sessions >= 30 AND engaged_sessions::numeric / NULLIF(sessions, 0) < 0.05)
            ) FILTER (WHERE event_name = 'session_start'),
            bool_or(engaged_sessions > 0)
        ) AS trafego_valido
    FROM expandido
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
)
INSERT INTO silver.ga4_eventos (
    event_date, hostname, site, country, region, city, device_category, browser,
    operating_system, event_name, event_count, sessions, engaged_sessions,
    active_users, user_engagement_seconds, trafego_valido, data_extracao
)
SELECT
    x.event_date, x.hostname, x.site, x.country, x.region, x.city, x.device_category,
    x.browser, x.operating_system, x.event_name, x.event_count, x.sessions,
    x.engaged_sessions, x.active_users, x.user_engagement_seconds,
    COALESCE(v.trafego_valido, x.engaged_sessions > 0),
    x.data_extracao
FROM expandido x
LEFT JOIN validade v USING
    (event_date, hostname, country, region, city, device_category, browser, operating_system);

-- =====================================================================
-- Report B -> silver.ga4_paineis
-- =====================================================================
CREATE TEMP TABLE _dias_painel ON COMMIT DROP AS
SELECT b.event_date
FROM bronze.ga4_paineis_raw b
GROUP BY b.event_date
HAVING max(b.data_extracao) > COALESCE(
    (SELECT max(s.data_extracao) FROM silver.ga4_paineis s WHERE s.event_date = b.event_date),
    '-infinity');

DELETE FROM silver.ga4_paineis WHERE event_date IN (SELECT event_date FROM _dias_painel);

WITH ultimo_snapshot AS (
    SELECT DISTINCT ON (event_date) event_date, payload, data_extracao
    FROM bronze.ga4_paineis_raw
    WHERE event_date IN (SELECT event_date FROM _dias_painel)
    ORDER BY event_date, data_extracao DESC
)
INSERT INTO silver.ga4_paineis (
    event_date, hostname, site, country, region, city, device_category, event_name,
    nome_painel_raw, event_count, sessions, engaged_sessions, active_users,
    user_engagement_seconds, data_extracao
)
SELECT
    (elem->>'date')::date,
    elem->>'hostName',
    silver.fn_site(elem->>'hostName'),
    COALESCE(NULLIF(elem->>'country', ''), '(not set)'),
    COALESCE(NULLIF(elem->>'region', ''), '(not set)'),
    COALESCE(NULLIF(elem->>'city', ''), '(not set)'),
    COALESCE(NULLIF(elem->>'deviceCategory', ''), '(not set)'),
    elem->>'eventName',
    COALESCE(NULLIF(elem->>'customEvent:nome_painel', ''), '(not set)'),
    (elem->>'eventCount')::bigint,
    (elem->>'sessions')::bigint,
    (elem->>'engagedSessions')::bigint,
    (elem->>'activeUsers')::bigint,
    (elem->>'userEngagementDuration')::numeric,
    s.data_extracao
FROM ultimo_snapshot s, jsonb_array_elements(s.payload) elem;

-- =====================================================================
-- Report C -> silver.ga4_usuarios
-- =====================================================================
CREATE TEMP TABLE _dias_usuarios ON COMMIT DROP AS
SELECT b.event_date
FROM bronze.ga4_usuarios_raw b
GROUP BY b.event_date
HAVING max(b.data_extracao) > COALESCE(
    (SELECT max(s.data_extracao) FROM silver.ga4_usuarios s WHERE s.event_date = b.event_date),
    '-infinity');

DELETE FROM silver.ga4_usuarios WHERE event_date IN (SELECT event_date FROM _dias_usuarios);

WITH ultimo_snapshot AS (
    SELECT DISTINCT ON (event_date) event_date, payload, data_extracao
    FROM bronze.ga4_usuarios_raw
    WHERE event_date IN (SELECT event_date FROM _dias_usuarios)
    ORDER BY event_date, data_extracao DESC
)
INSERT INTO silver.ga4_usuarios (
    event_date, hostname, site, country, device_category,
    dau, wau, mau, sessions, engaged_sessions, user_engagement_seconds, data_extracao
)
SELECT
    (elem->>'date')::date,
    elem->>'hostName',
    silver.fn_site(elem->>'hostName'),
    COALESCE(NULLIF(elem->>'country', ''), '(not set)'),
    COALESCE(NULLIF(elem->>'deviceCategory', ''), '(not set)'),
    (elem->>'active1DayUsers')::bigint,
    (elem->>'active7DayUsers')::bigint,
    (elem->>'active28DayUsers')::bigint,
    (elem->>'sessions')::bigint,
    (elem->>'engagedSessions')::bigint,
    (elem->>'userEngagementDuration')::numeric,
    s.data_extracao
FROM ultimo_snapshot s, jsonb_array_elements(s.payload) elem;

-- =====================================================================
-- Report D -> silver.ga4_paginas
-- =====================================================================
CREATE TEMP TABLE _dias_paginas ON COMMIT DROP AS
SELECT b.event_date
FROM bronze.ga4_paginas_raw b
GROUP BY b.event_date
HAVING max(b.data_extracao) > COALESCE(
    (SELECT max(s.data_extracao) FROM silver.ga4_paginas s WHERE s.event_date = b.event_date),
    '-infinity');

DELETE FROM silver.ga4_paginas WHERE event_date IN (SELECT event_date FROM _dias_paginas);

WITH ultimo_snapshot AS (
    SELECT DISTINCT ON (event_date) event_date, payload, data_extracao
    FROM bronze.ga4_paginas_raw
    WHERE event_date IN (SELECT event_date FROM _dias_paginas)
    ORDER BY event_date, data_extracao DESC
)
INSERT INTO silver.ga4_paginas (
    event_date, hostname, site, page_location, alvo,
    page_views, usuarios, usuarios_7d, usuarios_28d, data_extracao
)
SELECT
    (elem->>'date')::date,
    elem->>'hostName',
    silver.fn_site(elem->>'hostName'),
    elem->>'pageLocation',
    silver.fn_alvo_redirect(elem->>'pageLocation'),
    (elem->>'eventCount')::bigint,
    (elem->>'activeUsers')::bigint,
    (elem->>'active7DayUsers')::bigint,
    (elem->>'active28DayUsers')::bigint,
    s.data_extracao
FROM ultimo_snapshot s, jsonb_array_elements(s.payload) elem;
