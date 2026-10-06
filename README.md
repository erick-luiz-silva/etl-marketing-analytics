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
- [x] Carga histórica completa (site desde fev/2023; painéis desde jun/2026)
- [x] Carga incremental (`pipeline.py`) testada — janela D-3 → ontem
- [x] Usuários ativos DAU/WAU/MAU (Report C, teste 7)
- [x] Relatório semanal (`report/`) com usuários e médias + trava de semana incompleta
- [x] Dashboard Power BI (PBIP versionado em `BI/`) — correções do modelo em andamento
- [x] Agendamento no Task Scheduler (roda na cópia Windows — ver "Execução")
- [x] GTM: `nome_painel` canônico pelo ID do relatório (GTM v10, 2026-10-05) + aliases das grafias antigas
- [x] Validação contra o export BigQuery (eventos batem 100%; ver `testes/ACHADOS.md`, Teste 8)
- [x] `dim_painel`: `Competitividade Carne Suína` e `Mercado Global` cadastrados (ordem/público a definir)
- [x] Painéis contados pela URL (`?redirect=` → ID do relatório), independente do GTM (Report D, Teste 9)
- [ ] GA4: ativar filtro "Tráfego de desenvolvedor" (11% dos `painel_acessado` são Preview do GTM)
- [ ] Painéis: registrar `redirect_url`/`origem` como dimensão no GA4, modelar `origem`, deduplicar (futuro)

---

## O que os testes revelaram (e como o desenho responde)

| Achado | Resposta no pipeline |
|---|---|
| A Data API **não tem a dimensão `sessionEngaged`** (só o export BigQuery) | Filtro de bot por segmento: `trafego_valido` na Silver, decidido pela linha `session_start` |
| Bots atuais usam `browser = "Chrome"` / `OS = "Windows"` | Filtro por browser vazio **descartado** (não pega nada) |
| China = ~97% das sessões, 0% engajamento, só no site institucional | Segmento inválido = `sessions >= 30 AND taxa de engajamento < 5%`; `gold.vw_qualidade_trafego` monitora |
| Métricas de sessão/usuário repetem em cada linha de `eventName` | Gold lê essas métricas só de `gold.vw_sessoes` (recorte `session_start`) |
| Os 18 painéis do Data Insights são todos distintos; o GTM manda o nome canônico | `silver.dim_painel` (dimensão descritiva, seed do CSV do time) + match exato na Gold; `dim_painel_alias` p/ drift |
| ~~48% dos `painel_acessado` vêm com `nome_painel = (not set)`~~ — resolvido desde 29/08 (export BigQuery) | `(not set)` conta como `painel = NULL`, fora do ranking; GTM v10 manda o nome canônico pelo ID do relatório |
| Existe evento `painel_clicado` além de `painel_acessado` | Ambos entram em `gold.vw_painel_normalizado` |
| Evento de clique `painel_acessado` parou de ~19/09 a 05/10 (site mudou o menu) | **Report D**: aberturas pela URL `/relatorios/?redirect=` (ID do relatório Power BI no `r=`), mapa ID → painel em `silver.dim_painel_relatorio` |
| Incluir `customEvent:nome_painel` num relatório **corta o histórico** para ~jun/2026 (data de criação da dimensão) | **Dois relatórios**: Report A (site, sem a dimensão, desde fev/2023) e Report B (painéis, com a dimensão) |
| Painéis só têm dados reais desde 27/08/2026 | `DATA_INICIO_HISTORICO` (fev/2023) vs `DATA_INICIO_PAINEIS` (jun/2026) em `config.py` |
| Usuário não é aditivo entre dias; a soma por segmento fino infla +20–30% | **Report C**: `active1/7/28DayUsers` por data × host × país × dispositivo (infla ≤ 2%), regra de bot sobre a janela |
| A propriedade recebe hits de hosts que não são da ABCS | `silver.fn_site()` com lista explícita; o resto vira `'Outros'` e sai da gold |

---

## Arquitetura de dados

```
GA4 Data API  (propriedade 353835454, Service Account)
        │
        ├── Report A (uso do site, sem custom dim)      ── desde fev/2023
        ├── Report B (painéis, com customEvent:nome_painel,
        │             filtrado a painel_acessado/clicado) ── desde jun/2026
        ├── Report C (usuários ativos 1/7/28 dias, por
        │             host × país × dispositivo)            ── desde fev/2023
        └── Report D (page_views de /relatorios/?redirect=,
                      por URL → ID do relatório → painel)   ── desde jun/2026
        ▼
┌──────────────────────────────────────────────┐
│ BRONZE   1 linha por dia, JSON cru, append-only│
│  bronze.ga4_site_raw                           │
│  bronze.ga4_paineis_raw                        │
│  bronze.ga4_usuarios_raw                       │
│  bronze.ga4_paginas_raw                        │
│  bronze.controle_execucao (col. relatorio)     │
└──────────────────────────────────────────────┘
        │  substitui o dia inteiro (idempotente)
        ▼
┌──────────────────────────────────────────────┐
│ SILVER                                         │
│  ga4_eventos   site: achatada, coluna site,    │
│                coluna trafego_valido/segmento  │
│  ga4_paineis   eventos de painel + nome_painel │
│  ga4_usuarios  DAU/WAU/MAU + sessões por dia   │
│  ga4_paginas   aberturas de painel por URL     │
│  dim_painel_relatorio  ID do relatório → painel│
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
│  usuários: vw_usuarios_ativos (DAU/WAU/MAU)    │
│  painéis (oficial): vw_paineis_acessos,        │
│           vw_paineis_url_sem_mapa (auditoria)  │
└──────────────────────────────────────────────┘
        │
        ▼
   Power BI Desktop  (conexão direta PostgreSQL)
```

### Grão dos relatórios

**Report A (site):** `date, hostName, country, region, city, deviceCategory,
browser, operatingSystem, eventName` (9 = máximo). Serve das tabelas agregadas
do GA4 → alcança fev/2023.

**Report B (painéis):** `date, hostName, country, region, city, deviceCategory,
eventName, customEvent:nome_painel`, filtrado a `painel_acessado` /
`painel_clicado`. A dimensão personalizada limita o histórico a ~jun/2026.

`region` = estado/província (o GA4 devolve "State of São Paulo", "Federal
District", "Ceara" — grafia em inglês, mantida crua na silver).

Métricas (A e B): `eventCount`, `sessions`, `engagedSessions`, `activeUsers`,
`userEngagementDuration`.

**Report C (usuários):** `date, hostName, country, deviceCategory` com
`active1DayUsers`, `active7DayUsers`, `active28DayUsers` (usuários únicos de
1/7/28 dias até `date`), `sessions`, `engagedSessions`, `userEngagementDuration`.
WAU = `active7DayUsers` do domingo (semana seg–dom); MAU = 28 dias móveis.
Para um período, ler wau/mau do **último dia** — nunca somar entre dias.

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
├── report/                       relatório semanal (PDF + texto WhatsApp)
├── BI/                           Power BI (PBIP: Report + SemanticModel)
├── CHANGELOG.md                  mudanças relevantes de dados/modelo/entregáveis
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
python extract_bronze.py     # site e usuários desde fev/2023 + painéis desde jun/2026
```

Flags: `--inicio-site`, `--inicio-painel`, `--fim` (ISO), `--relatorios`
(ex.: `--relatorios usuarios` para carregar só um). Ao final já roda a
transformação da silver.

A silver só reprocessa os dias com snapshot novo na bronze. Ao mudar uma regra
de `sql/transform_bronze_to_silver.sql`: `python load_silver.py --completo`.

### Carga diária

```powershell
python pipeline.py
```

Extrai a janela pendente (D-3 no mínimo, mais larga se ficou dias sem rodar),
grava na bronze, re-aplica a silver e confere as views gold. Loga em
`logs/pipeline.log`.

### Produção (Task Scheduler)

O desenvolvimento é no WSL; a carga diária roda numa **cópia Windows do mesmo
repositório** (`C:\Users\User\Desktop\erick\projetos\marketing-analytics`), tarefa
`ScriptDiarioMonitoramento_Marketing` às 17:00 → `src\executar.bat` (Anaconda).

- Deploy: `git push` no WSL → `git pull` na cópia Windows. Mudou schema SQL →
  `python src\setup_db.py` lá também.
- Na tarefa, marcar **"Executar a tarefa o mais cedo possível após uma
  inicialização agendada ser perdida"** — sem isso, PC desligado às 17h = dia sem carga
  (a janela incremental recupera depois, mas o relatório de segunda pode pegar a
  semana incompleta).

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
- **Conferência contra o bruto:** o export GA4 → BigQuery
  (`thermal-history-506217-c4.analytics_353835454`, desde 27/08/2026) é a
  referência para validar a silver — ver `testes/ACHADOS.md`, Teste 8.
- A GA4 processa dados com 24–48h de atraso; a janela incremental já recua 3 dias.
