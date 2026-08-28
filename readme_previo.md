# ABCS Analytics — Pipeline GA4

Pipeline de extração, tratamento e análise dos dados de acesso aos
portais da ABCS, com arquitetura Medallion local
(Bronze → Silver → Gold) e visualização no Power BI Desktop.

---

## Contexto

A ABCS opera dois portais públicos monitorados por este pipeline:

| Portal | Domínio | Foco |
|--------|---------|------|
| ABCS Data Insights | abcsdata.abcs.org.br | 17 painéis de inteligência de mercado da suinocultura |
| Site Institucional | abcs.org.br | Publicações, notícias e informações da associação |

Ambos compartilham a mesma propriedade GA4 (`G-G51E1LJEWJ`,
ID `353835454`) e são diferenciados pela dimensão `hostname`.

O pipeline extrai os dados pela GA4 Data API, remove tráfego
robótico por critérios comportamentais (não por país), e entrega
um modelo analítico para orientar decisões de produto — quais
painéis priorizar no redesign mobile, qual o engajamento real
por painel e como o público usa o site institucional.

---

## Contexto de qualidade dos dados

### Diagnóstico de bots (agosto/2026)

A auditoria identificou tráfego automatizado significativo:

| País | Eventos | Sessões engajadas | % Engajamento |
|------|---------|-------------------|---------------|
| China | 9.619 | 5 | 0,05% |
| Brasil | 1.139 | 635 | 55,75% |
| EUA | 156 | 38 | 24,36% |

Padrões identificados nos bots:
- Windows + browser vazio (headless Chrome) respondem por ~99%
  do tráfego suspeito
- `is_active_user = true` em 100% dos casos da China — a detecção
  nativa do GA4 não captura esses bots
- Quase zero `engagement_time_msec` nas sessões suspeitas

### Filtros aplicados na camada Silver

| Filtro | Critério | Justificativa |
|--------|----------|---------------|
| Engajamento de sessão | `sessionEngaged = '1'` | Remove 99,95% dos bots; mantém 55,75% do Brasil |
| Browser headless | `browser != ''` | Captura residual com headless Chrome sem engajamento |

**Nenhum filtro por país.** O setor suinícola tem mercado ativo
na Ásia — usuários legítimos do Japão, Vietnam e outros países
asiáticos são esperados e preservados.

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Coleta | Google Tag Manager + GA4 |
| Extração | Python + GA4 Data API v1 |
| Armazenamento | PostgreSQL local |
| Agendamento | Windows Task Scheduler |
| Visualização | Power BI Desktop |

---

## Estrutura do projeto

abcs-analytics/
├── config/
│ └── credentials.json # Service Account key — não commitar
├── extraction/
│ └── ga4_client.py # Conexão e chamadas à GA4 Data API
├── pipeline/
│ ├── bronze_load.py # Insere dados brutos separados por site
│ ├── silver_transform.py # Filtros de bot e normalização
│ └── gold_views.py # Cria/atualiza views analíticas
├── scheduler/
│ └── run_daily.py # Ponto de entrada do Task Scheduler
├── sql/
│ ├── 01_create_schemas.sql
│ ├── 02_create_bronze.sql
│ ├── 03_create_silver.sql
│ └── 04_create_gold.sql
├── .gitignore
├── requirements.txt
└── README.md


---

## Autenticação

O pipeline usa **Service Account** — nenhum token expira,
nenhuma intervenção manual é necessária. A biblioteca
`google-auth` renova os tokens de curta duração internamente
a partir do arquivo `credentials.json`.

Isso difere da abordagem OAuth 2.0 (tokens de 1 hora com
refresh manual) — Service Account é a única opção viável
para pipelines automatizados sem usuário presente.

---

## Pré-requisitos

- Python 3.10+
- PostgreSQL 14+ rodando localmente
- Service Account com acesso de **Leitura** à propriedade
  GA4 `353835454` — arquivo JSON em `config/credentials.json`
- Power BI Desktop instalado

---

## Configuração

### 1. Instalar dependências

```bash
git clone <repo>
cd abcs-analytics
pip install -r requirements.txt
```

`requirements.txt`:

google-auth==2.29.0
google-auth-httplib2==0.2.0
requests==2.31.0
psycopg2-binary==2.9.9
python-dotenv==1.0.1


### 2. Variáveis de ambiente

Crie `.env` na raiz:

GA4_PROPERTY_ID=353835454
GA4_CREDENTIALS_PATH=config/credentials.json

DB_HOST=localhost
DB_PORT=5432
DB_NAME=abcs_analytics
DB_USER=seu_usuario
DB_PASSWORD=sua_senha


### 3. Criar o banco de dados

```bash
psql -U seu_usuario -c "CREATE DATABASE abcs_analytics;"
psql -U seu_usuario -d abcs_analytics -f sql/01_create_schemas.sql
psql -U seu_usuario -d abcs_analytics -f sql/02_create_bronze.sql
psql -U seu_usuario -d abcs_analytics -f sql/03_create_silver.sql
psql -U seu_usuario -d abcs_analytics -f sql/04_create_gold.sql
```

---

## Arquitetura de dados

GA4 Data API (propriedade 353835454)
│
│ dimensão hostname diferencia os dois sites
│
┌─────┴──────┐
│ │
abcsdata abcs.org.br
│ │
▼ ▼
┌─────────────────────────────────────────┐
│ BRONZE │
│ bronze.ga4_abcsdata_raw │
│ bronze.ga4_institucional_raw │
│ Dados brutos da API, append-only │
│ Uma linha por dimensão/data/hostname │
└─────────────────────────────────────────┘
│
│ sessionEngaged = '1' + browser != ''
▼
┌─────────────────────────────────────────┐
│ SILVER silver.ga4_events │
│ Tabela unificada com coluna site │
│ Bots removidos por comportamento │
│ nome_painel normalizado │
└─────────────────────────────────────────┘
│
│ Agregações e regras de negócio
▼
┌─────────────────────────────────────────┐
│ GOLD — views analíticas │
│ │
│ Data Insights: │
│ vw_paineis_ranking │
│ vw_engajamento_dispositivo │
│ │
│ Institucional: │
│ vw_paginas_mais_acessadas │
│ vw_trafego_por_origem │
│ │
│ Consolidado: │
│ vw_site_overview │
└─────────────────────────────────────────┘
│
▼
Power BI Desktop
(conexão direta PostgreSQL)


---

## Modelo de dados

### Bronze — duas tabelas, estrutura idêntica

```sql
-- Repetir para bronze.ga4_institucional_raw
CREATE TABLE bronze.ga4_abcsdata_raw (
    id                  SERIAL PRIMARY KEY,
    extraction_date     DATE NOT NULL,       -- data em que o script rodou
    event_date          DATE NOT NULL,       -- data do evento no GA4
    event_name          VARCHAR(100),
    nome_painel         VARCHAR(200),        -- parâmetro customizado (só abcsdata)
    hostname            VARCHAR(100),        -- abcsdata.abcs.org.br
    device_category     VARCHAR(50),         -- desktop / mobile / tablet
    browser             VARCHAR(100),
    operating_system    VARCHAR(100),
    country             VARCHAR(100),
    city                VARCHAR(100),
    session_engaged     VARCHAR(5),          -- '1' ou '0'
    active_users        INTEGER,
    event_count         INTEGER,
    sessions            INTEGER,
    engaged_sessions    INTEGER,
    engagement_seconds  NUMERIC(10,2),
    loaded_at           TIMESTAMP DEFAULT NOW()
);
```

### Silver — filtrada e normalizada

```sql
CREATE TABLE silver.ga4_events AS
SELECT
    event_date,
    event_name,
    hostname,

    -- Identifica o site pela origem
    CASE
        WHEN hostname ILIKE '%abcsdata%' THEN 'Data Insights'
        ELSE 'Institucional'
    END AS site,

    -- Normaliza variações de grafia do mesmo painel
    CASE
        WHEN nome_painel ILIKE '%cepea%'
            THEN 'Cotações Suínos - CEPEA'
        WHEN nome_painel ILIKE '%bolsa%'
            THEN 'Cotações - Bolsas Estaduais'
        WHEN nome_painel ILIKE '%referên%'
          OR nome_painel ILIKE '%referenc%'
            THEN 'Preços de Referência'
        WHEN nome_painel ILIKE '%insumo%'
            THEN 'Insumos'
        WHEN nome_painel ILIKE '%custo%'
            THEN 'Custos de Produção'
        WHEN nome_painel ILIKE '%comér%'
          OR nome_painel ILIKE '%comer%'
            THEN 'Comércio Exterior'
        WHEN nome_painel ILIKE '%ibge%'
            THEN 'IBGE Abate'
        WHEN nome_painel ILIKE '%sif%abate%'
          OR nome_painel ILIKE '%abate%sif%'
            THEN 'SIF Abate'
        WHEN nome_painel ILIKE '%emprego%perfil%'
          OR nome_painel ILIKE '%rais%'
            THEN 'Emprego - Perfil'
        WHEN nome_painel ILIKE '%emprego%movim%'
          OR nome_painel ILIKE '%caged%'
            THEN 'Emprego - Movimentação'
        WHEN nome_painel ILIKE '%crédito%suino%'
          OR nome_painel ILIKE '%credito%suino%'
            THEN 'Crédito Rural - Suinocultura'
        WHEN nome_painel ILIKE '%program%'
          OR nome_painel ILIKE '%recurso%'
            THEN 'Crédito Rural - Programas'
        WHEN nome_painel ILIKE '%estabeleciment%'
            THEN 'SIF Estabelecimentos'
        WHEN nome_painel ILIKE '%cenário%'
          OR nome_painel ILIKE '%cenario%'
            THEN 'Cenário Empresarial'
        WHEN nome_painel ILIKE '%matrize%'
            THEN 'Matrizes Tecnificadas'
        WHEN nome_painel ILIKE '%competi%'
            THEN 'Competitividade'
        WHEN nome_painel ILIKE '%mercado%global%'
          OR nome_painel ILIKE '%usda%'
            THEN 'Mercado Global'
        ELSE nome_painel
    END AS nome_painel_norm,

    device_category,
    browser,
    operating_system,
    country,
    city,
    active_users,
    event_count,
    sessions,
    engaged_sessions,
    engagement_seconds

FROM bronze.ga4_abcsdata_raw

WHERE session_engaged = '1'   -- filtro primário de bot
  AND browser != ''            -- remove headless Chrome

UNION ALL

SELECT
    event_date, event_name, hostname,
    'Institucional' AS site,
    NULL AS nome_painel_norm,
    device_category, browser, operating_system,
    country, city, active_users, event_count,
    sessions, engaged_sessions, engagement_seconds
FROM bronze.ga4_institucional_raw
WHERE session_engaged = '1'
  AND browser != '';
```

### Gold — views por domínio analítico

```sql
-- Ranking de painéis (Data Insights)
CREATE VIEW gold.vw_paineis_ranking AS
SELECT
    event_date,
    nome_painel_norm                AS painel,
    SUM(event_count)                AS acessos,
    SUM(sessions)                   AS sessoes,
    SUM(active_users)               AS usuarios,
    SUM(engaged_sessions)           AS sessoes_engajadas,
    ROUND(SUM(engagement_seconds) / NULLIF(SUM(sessions), 0), 1)
                                    AS tempo_medio_seg,
    COUNT(DISTINCT device_category) AS dispositivos_distintos
FROM silver.ga4_events
WHERE event_name = 'painel_acessado'
  AND nome_painel_norm IS NOT NULL
GROUP BY 1, 2;

-- Engajamento por dispositivo (Data Insights)
CREATE VIEW gold.vw_engajamento_dispositivo AS
SELECT
    event_date,
    nome_painel_norm    AS painel,
    device_category     AS dispositivo,
    SUM(sessions)       AS sessoes,
    SUM(active_users)   AS usuarios,
    SUM(engagement_seconds) AS tempo_engajamento_s
FROM silver.ga4_events
WHERE site = 'Data Insights'
  AND event_name = 'painel_acessado'
GROUP BY 1, 2, 3;

-- Páginas mais acessadas (Institucional)
CREATE VIEW gold.vw_paginas_mais_acessadas AS
SELECT
    event_date,
    event_name,
    country,
    device_category,
    SUM(event_count)    AS pageviews,
    SUM(active_users)   AS usuarios,
    SUM(sessions)       AS sessoes
FROM silver.ga4_events
WHERE site = 'Institucional'
GROUP BY 1, 2, 3, 4;

-- Tráfego por origem (Institucional)
CREATE VIEW gold.vw_trafego_por_origem AS
SELECT
    event_date,
    country,
    device_category,
    SUM(sessions)           AS sessoes,
    SUM(active_users)       AS usuarios,
    SUM(engagement_seconds) AS tempo_total_s
FROM silver.ga4_events
WHERE site = 'Institucional'
GROUP BY 1, 2, 3;

-- Visão consolidada dos dois sites
CREATE VIEW gold.vw_site_overview AS
SELECT
    event_date,
    site,
    device_category,
    country,
    SUM(active_users)       AS usuarios,
    SUM(sessions)           AS sessoes,
    SUM(engaged_sessions)   AS sessoes_engajadas,
    SUM(engagement_seconds) AS tempo_engajamento_s
FROM silver.ga4_events
GROUP BY 1, 2, 3, 4;
```

---

## Execução

### Carga histórica (uma vez)

```bash
python scheduler/run_daily.py --mode historico --inicio 2026-08-27
```

A data de início é 27/08/2026 — quando a tag `painel_acessado`
e a dimensão personalizada `nome_painel` foram ativadas no GA4.
Dados anteriores não têm o parâmetro preenchido.

### Carga incremental (diária)

```bash
python scheduler/run_daily.py --mode incremental
```

Extrai o dia anterior, insere no bronze, re-aplica silver e
atualiza as views gold.

### Agendamento no Windows Task Scheduler

1. Nova tarefa básica → nome: `ABCS Analytics — Carga Diária`
2. Gatilho: todos os dias às **06:00**
3. Ação: `python C:\caminho\abcs-analytics\scheduler\run_daily.py --mode incremental`
4. Marcar: "Executar mesmo que o usuário não esteja conectado"

---

## Rastreamento GTM — contexto

### Data Insights — evento painel_acessado

Captura cliques nos painéis em dois fluxos:

| Fluxo | Elemento | Parâmetros |
|-------|----------|------------|
| A — Homepage | `a[href*="redirect="]` | `nome_painel` + `redirect_url` |
| B — /relatorios/ | `a[onclick*="mudarIframe"]` | `nome_painel` |

O GTM está instalado atualmente na homepage e em `/relatorios/`.

### Institucional — eventos monitorados

| Evento GA4 | O que mede |
|------------|-----------|
| `page_view` | Páginas visitadas |
| `scroll` | Profundidade de leitura |
| `session_start` | Início de sessão |
| `user_engagement` | Tempo ativo na página |

---

## Observações importantes

- **Números brutos da Bronze nunca reportar ao marketing** —
  incluem tráfego robótico. Usar sempre as views Gold.
- A dimensão `nome_painel` foi registrada em 27/08/2026 —
  eventos anteriores retornam `(not set)` nesse parâmetro.
- `is_active_user` do GA4 não detecta os bots identificados
  (China aparece como `true` em 100% dos casos) — os filtros
  comportamentais da Silver são mais eficazes que a detecção nativa.
- Ao adicionar novos painéis à plataforma, atualizar o CASE WHEN
  de normalização na Silver para incluir o novo painel.