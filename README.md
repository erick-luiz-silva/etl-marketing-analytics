# ABCS Marketing Analytics — Pipeline GA4

Pipeline de extração, tratamento e análise dos acessos aos portais da ABCS,
com arquitetura Medallion local (Bronze → Silver → Gold) e consumo no
Power BI Desktop.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-4169E1?logo=postgresql&logoColor=white)
![Status](https://img.shields.io/badge/status-esqueleto-lightgrey)

---

## Sobre o projeto

A ABCS opera dois portais públicos na **mesma propriedade GA4** (`353835454`),
diferenciados pela dimensão `hostName`:

| Portal | Domínio | Foco |
|---|---|---|
| ABCS Data Insights | `abcsdata.abcs.org.br` | painéis de inteligência de mercado da suinocultura |
| Site Institucional | `abcs.org.br` | publicações, notícias e informações da associação |

O pipeline extrai os dados pela GA4 Data API, remove tráfego robótico por
critério comportamental (**não por país** — o setor tem mercado legítimo na
Ásia) e entrega um modelo analítico para orientar decisões de produto: quais
painéis priorizar, qual o engajamento real por painel, como o público usa o
site institucional.

O método segue o projeto `monitoramento_proposicoes`: infraestrutura local,
Bronze cru append-only, Silver normalizada e idempotente, regras de negócio
só na Gold.

---

## Estado atual

Extração validada por 5 testes de API documentados em
[`testes/ACHADOS.md`](testes/ACHADOS.md). Banco criado, schemas aplicados,
`dim_painel` populada, carga de teste (ago/2026) validada nas views.

- [x] Cliente GA4 (Service Account + retry + paginação)
- [x] Scripts de teste exploratório (`testes/01`–`05`)
- [x] Schemas SQL bronze / silver / gold + transformação
- [x] `silver.dim_painel` a partir do CSV do time
- [x] Orquestração (`extract_bronze`, `extract_incremental`, `pipeline`)
- [ ] Carga histórica completa (desde fev/2023)
- [ ] Teste da carga incremental / `pipeline.py`
- [ ] Dashboard Power BI
- [ ] Agendamento no Task Scheduler
- [ ] GTM: corrigir 48% de `nome_painel = (not set)` (fora deste repo)

---

## O que os testes revelaram (e como o desenho responde)

| Achado | Resposta no pipeline |
|---|---|
| A Data API **não tem a dimensão `sessionEngaged`** (só o export BigQuery) | Filtro de bot por segmento: `trafego_valido` na Silver, decidido pela linha `session_start` |
| Bots atuais usam `browser = "Chrome"` / `OS = "Windows"` | Filtro por browser vazio **descartado** (não pega nada) |
| China = ~97% das sessões, 0% engajamento, só no site institucional | Segmento inválido = `sessions >= 30 AND taxa de engajamento < 5%`; `gold.vw_qualidade_trafego` monitora |
| Métricas de sessão/usuário repetem em cada linha de `eventName` | Gold lê essas métricas só de `gold.vw_sessoes` (recorte `session_start`) |
| Os 18 painéis do Data Insights são todos distintos; o GTM manda o nome canônico | `silver.dim_painel` (dimensão descritiva, seed do CSV do time) + match exato na Gold; `dim_painel_alias` p/ drift |
| 48% dos `painel_acessado` vêm com `nome_painel = (not set)` | contam como `painel = NULL`, fora do ranking; problema é de GTM (fora do repo) |
| Existe evento `painel_clicado` além de `painel_acessado` | Ambos entram em `gold.vw_painel_normalizado` |
| Incluir `customEvent:nome_painel` num relatório **corta o histórico** para ~jun/2026 (data de criação da dimensão) | **Dois relatórios**: Report A (site, sem a dimensão, desde fev/2023) e Report B (painéis, com a dimensão) |
| Painéis só têm dados reais desde 27/08/2026 | `DATA_INICIO_HISTORICO` (fev/2023) vs `DATA_INICIO_PAINEIS` (jun/2026) em `config.py` |

---

## Arquitetura de dados

```
GA4 Data API  (propriedade 353835454, Service Account)
        │
        ├── Report A (uso do site, sem custom dim)      ── desde fev/2023
        └── Report B (painéis, com customEvent:nome_painel,
                      filtrado a painel_acessado/clicado) ── desde jun/2026
        ▼
┌──────────────────────────────────────────────┐
│ BRONZE   1 linha por dia, JSON cru, append-only│
│  bronze.ga4_site_raw                           │
│  bronze.ga4_paineis_raw                        │
│  bronze.controle_execucao (col. relatorio)     │
└──────────────────────────────────────────────┘
        │  substitui o dia inteiro (idempotente)
        ▼
┌──────────────────────────────────────────────┐
│ SILVER                                         │
│  ga4_eventos   site: achatada, coluna site,    │
│                coluna trafego_valido/segmento  │
│  ga4_paineis   eventos de painel + nome_painel │
│  dim_painel        dimensão dos 18 painéis      │
│  dim_painel_alias  apelidos GA4 → painel        │
└──────────────────────────────────────────────┘
        │  WHERE trafego_valido (site) + normalização de painel
        ▼
┌──────────────────────────────────────────────┐
│ GOLD — views                                  │
│  site:    vw_sessoes (base), vw_site_overview, │
│           vw_institucional_eventos,            │
│           vw_qualidade_trafego (auditoria)     │
│  painéis: vw_painel_normalizado,               │
│           vw_paineis_ranking,                  │
│           vw_engajamento_dispositivo,          │
│           vw_paineis_sem_mapeamento (auditoria)│
└──────────────────────────────────────────────┘
        │
        ▼
   Power BI Desktop  (conexão direta PostgreSQL)
```

### Grão dos relatórios

**Report A (site):** `date, hostName, country, city, deviceCategory, browser,
operatingSystem, eventName`. Serve das tabelas agregadas do GA4 → alcança fev/2023.

**Report B (painéis):** `date, hostName, country, city, deviceCategory,
eventName, customEvent:nome_painel`, filtrado a `painel_acessado` /
`painel_clicado`. A dimensão personalizada limita o histórico a ~jun/2026.

Métricas (ambos): `eventCount`, `sessions`, `engagedSessions`, `activeUsers`,
`userEngagementDuration`.

---

## Estrutura do projeto

```
marketing-analytics/
├── config/
│   └── credentials.json          Service Account (gitignored)
├── data/                         CSVs do time, ex. painéis (gitignored)
├── src/
│   ├── config.py                 DB + constantes da API + datas de corte
│   ├── db.py                     get_connection()
│   ├── ga4_client.py             auth SA, runReport, paginação, retry
│   ├── setup_db.py               aplica os 3 schemas
│   ├── load_dimensoes.py         aplica sql/seed_dim_painel.sql
│   ├── load_bronze.py            grava snapshot diário na bronze
│   ├── load_silver.py            executa a transformação bronze → silver
│   ├── extract_bronze.py         carga histórica (mês a mês)
│   ├── extract_incremental.py    carga diária (janela auto-ajustável)
│   └── pipeline.py               ponto de entrada do Task Scheduler
├── sql/
│   ├── schema_bronze.sql         ga4_site_raw + ga4_paineis_raw + controle
│   ├── schema_silver.sql         ga4_eventos + ga4_paineis + dim_painel(+alias)
│   ├── schema_gold.sql
│   ├── seed_dim_painel.sql       snapshot dos 18 painéis (do CSV do time)
│   └── transform_bronze_to_silver.sql
├── testes/                       scripts exploratórios + ACHADOS.md
├── readme_previo.md              desenho original (histórico — superado por este)
├── .env.example
└── requirements.txt
```

---

## Configuração

### 1. Dependências

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Credenciais

- `config/credentials.json` — chave da Service Account. A conta
  (`gcp-221@thermal-history-506217-c4.iam.gserviceaccount.com`) precisa do
  papel **Leitor** em *GA4 Admin › Gerenciamento de acesso à propriedade*.
- `cp .env.example .env` e preencher a senha do Postgres.

### 3. Banco

```powershell
psql -U postgres -c "CREATE DATABASE abcs_marketing_analytics;"
cd src
python setup_db.py          # schemas bronze, silver, gold
python load_dimensoes.py    # aplica sql/seed_dim_painel.sql (18 painéis)
```

`sql/seed_dim_painel.sql` é o snapshot versionado de
`data/ABCS Data Insights - Painéis.csv` (mantido pelo time, fora do git).
Ao mudar os painéis, editar o seed e rodar `load_dimensoes.py` de novo.

---

## Execução

### Carga histórica (uma vez)

```powershell
python extract_bronze.py     # site desde fev/2023 + painéis desde jun/2026
```

Flags: `--inicio-site`, `--inicio-painel`, `--fim` (ISO). Ao final já roda a
transformação da silver.

### Carga diária

```powershell
python pipeline.py
```

Extrai a janela pendente (D-3 no mínimo, mais larga se ficou dias sem rodar),
grava na bronze, re-aplica a silver e confere as views gold. Loga em
`logs/pipeline.log`.

### Task Scheduler

1. Nova tarefa → *ABCS Marketing Analytics — Carga Diária*
2. Gatilho: todo dia às 06:00
3. Ação: `…\venv\Scripts\python.exe …\src\pipeline.py`
4. Marcar "Executar mesmo que o usuário não esteja conectado"

---

## Observações

- **Nunca reportar números da Bronze** — incluem tráfego robótico. Usar
  sempre as views Gold (já filtram `trafego_valido`).
- `nome_painel` só existe desde **27/08/2026**; eventos anteriores retornam
  `(not set)`.
- **Painéis são preliminares.** `painel_acessado` e `painel_clicado` duplicam em
  `/relatorios/` e a deduplicação depende de registrar `redirect_url` como
  dimensão no GA4 (adiado — feature futura). Até lá, o dashboard usa o Report A
  (uso do site); o ranking de painel só depois de dado limpo. Ver `testes/ACHADOS.md`.
- Ao surgir um painel novo (ou mudar a classificação), editar
  `sql/seed_dim_painel.sql` a partir do CSV do time e rodar `load_dimensoes.py`
  — não reprocessa a extração. Se o GTM mandar uma grafia diferente do nome
  canônico, adicionar linha em `silver.dim_painel_alias` (no mesmo seed).
  `gold.vw_paineis_sem_mapeamento` lista as grafias ainda sem correspondência.
- A GA4 processa dados com 24–48h de atraso; a janela incremental já recua 3 dias.
