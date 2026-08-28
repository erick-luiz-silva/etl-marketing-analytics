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

Esqueleto montado. Extração validada por 5 testes de API documentados em
[`testes/ACHADOS.md`](testes/ACHADOS.md). **Ainda não houve carga no banco.**

- [x] Cliente GA4 (Service Account + retry + paginação)
- [x] Scripts de teste exploratório (`testes/01`–`05`)
- [x] Schemas SQL bronze / silver / gold + transformação
- [x] Orquestração (`extract_bronze`, `extract_incremental`, `pipeline`)
- [ ] Criação do banco e carga histórica
- [ ] Dashboard Power BI
- [ ] Agendamento no Task Scheduler
- [ ] GTM: corrigir 48% de `nome_painel = (not set)` (fora deste repo)

---

## O que os testes revelaram (e como o desenho responde)

| Achado | Resposta no pipeline |
|---|---|
| A Data API **não tem a dimensão `sessionEngaged`** (só o export BigQuery) | Filtro de bot vira `trafego_valido = engaged_sessions > 0`, coluna na Silver |
| Bots atuais usam `browser = "Chrome"` / `OS = "Windows"` | Filtro por browser vazio **descartado** (não pega nada) |
| China = ~96% das sessões, 0% engajamento, só no site institucional | `gold.vw_qualidade_trafego` monitora quanto é descartado |
| `nome_painel` tem grafias livres e 48% `(not set)` | Normalização por regex na **Gold** (`silver.dim_painel`), ajustável sem reprocessar |
| Existe evento `painel_clicado` além de `painel_acessado` | Ambos entram em `gold.vw_painel_normalizado` |
| Histórico desde fev/2023; painéis só desde 27/08/2026 | `DATA_INICIO_HISTORICO` vs `DATA_INICIO_PAINEIS` em `config.py` |
| Só 588 linhas/dia no grão completo | Uma chamada por dia/mês, paginação por offset como salvaguarda |

---

## Arquitetura de dados

```
GA4 Data API  (propriedade 353835454, Service Account)
        │  runReport — 9 dimensões × 5 métricas
        ▼
┌──────────────────────────────────────────────┐
│ BRONZE  bronze.ga4_eventos_raw               │
│ 1 linha por dia, payload JSON cru, append-only│
│ bronze.controle_execucao — janela de cada run │
└──────────────────────────────────────────────┘
        │  substitui o dia inteiro (idempotente)
        ▼
┌──────────────────────────────────────────────┐
│ SILVER  silver.ga4_eventos                    │
│ achatada e normalizada, TODAS as linhas       │
│ coluna site (deriva de hostName)              │
│ coluna trafego_valido (engaged_sessions > 0)  │
│ silver.dim_painel — mapa de grafias           │
└──────────────────────────────────────────────┘
        │  WHERE trafego_valido + normalização de painel
        ▼
┌──────────────────────────────────────────────┐
│ GOLD — views                                  │
│  vw_painel_normalizado                         │
│  vw_paineis_ranking                            │
│  vw_engajamento_dispositivo                    │
│  vw_institucional_eventos                      │
│  vw_site_overview                              │
│  vw_qualidade_trafego        (auditoria)       │
│  vw_paineis_sem_mapeamento   (auditoria)       │
└──────────────────────────────────────────────┘
        │
        ▼
   Power BI Desktop  (conexão direta PostgreSQL)
```

### Grão da extração

9 dimensões (máximo do runReport): `date`, `hostName`, `country`, `city`,
`deviceCategory`, `browser`, `operatingSystem`, `eventName`,
`customEvent:nome_painel`.
5 métricas: `eventCount`, `sessions`, `engagedSessions`, `activeUsers`,
`userEngagementDuration`.

Origem de tráfego (`sessionDefaultChannelGroup`) não cabe nas 9 dimensões —
entraria como um segundo relatório se necessário.

---

## Estrutura do projeto

```
marketing-analytics/
├── config/
│   └── credentials.json          Service Account (gitignored)
├── src/
│   ├── config.py                 DB + constantes da API + datas de corte
│   ├── db.py                     get_connection()
│   ├── ga4_client.py             auth SA, runReport, paginação, retry
│   ├── paineis.py                mapa grafia → nome canônico (seed da dim_painel)
│   ├── setup_db.py               aplica os 3 schemas
│   ├── load_dimensoes.py         popula silver.dim_painel
│   ├── load_bronze.py            grava snapshot diário na bronze
│   ├── load_silver.py            executa a transformação bronze → silver
│   ├── extract_bronze.py         carga histórica (mês a mês)
│   ├── extract_incremental.py    carga diária (janela auto-ajustável)
│   └── pipeline.py               ponto de entrada do Task Scheduler
├── sql/
│   ├── schema_bronze.sql
│   ├── schema_silver.sql
│   ├── schema_gold.sql
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
python load_dimensoes.py    # popula silver.dim_painel
```

---

## Execução

### Carga histórica (uma vez)

```powershell
python extract_bronze.py                      # desde fev/2023
python extract_bronze.py --inicio 2026-06-01  # ou um recorte
```

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
- Ao surgir um painel novo, adicionar o mapeamento em `src/paineis.py` e
  rodar `load_dimensoes.py` — não precisa reprocessar a extração.
  `gold.vw_paineis_sem_mapeamento` lista as grafias ainda não mapeadas.
- A GA4 processa dados com 24–48h de atraso; a janela incremental já recua 3 dias.
