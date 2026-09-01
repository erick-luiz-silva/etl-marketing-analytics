# Achados dos testes de API — GA4 (propriedade 353835454)

Data: 2026-08-28 · Auth: Service Account `gcp-221@thermal-history-506217-c4.iam.gserviceaccount.com`

## Teste 1 — Autenticação
- Service Account (`config/credentials.json`) funciona com escopo `analytics.readonly`. Sem expiração, sem intervenção. É o caminho do readme.
- O `refresh_token` OAuth em `config/json_com_dados.json` também funcionava, mas é redundante agora. **Apagar esse arquivo** (tem client_secret + refresh_token em texto puro).

## Teste 2 — Metadata da propriedade
- 376 dimensões, 89 métricas disponíveis.
- Dimensão personalizada: **`customEvent:nome_painel`** (uiName "nome_painel"), escopo de evento. É a única custom relevante.
- Nenhuma métrica personalizada.
- **`sessionEngaged` NÃO existe como dimensão na Data API** (só no export BigQuery). O filtro primário de bot do readme (`session_engaged = '1'`) precisa ser trocado — ver Teste 4.
- Existem: `hostName`, `browser`, `deviceCategory`, `country`, `city`, `eventName`, `operatingSystem`.
- Conceito "engajada" na Data API só via métricas: `engagedSessions`, `engagementRate`, `userEngagementDuration`.

## Teste 3 — Evento painel_acessado
- Dados só desde 27/08/2026 (77 eventos até agora — volume ainda ínfimo).
- **48% dos `painel_acessado` vêm com `nome_painel = "(not set)"`** — a tag GTM não está passando o parâmetro em todos os fluxos. Investigar no GTM antes de confiar no ranking de painéis.
- Só `abcsdata.abcs.org.br` gera eventos de painel (esperado).

### `painel_acessado` vs `painel_clicado` — duplicação (análise ago/2026)
Dois eventos rastreiam abertura de painel e **disparam juntos em `/relatorios/`**:

| | `painel_clicado` (tag antiga, da empresa do site) | `painel_acessado` (tag que criamos) |
|---|---|---|
| onde dispara | só `/relatorios/` (clique no rótulo) | `/relatorios/` (72 ev) **e** `/` (6 ev) |
| `nome_painel` | 100% (42/42) | 81% (62/76) |
| extras | param `pagina` | `redirect_url` (fluxo homepage), UTM de evento |
| ruído de teste | nenhum | ~30% com referrer `gtm_debug=` / `_gl=` / `tagassistant` |

- **Fluxo A (card na homepage)**: `painel_acessado` dispara na página `/relatorios/`
  de destino (não na `/`); só o `redirect_url` distingue de um clique de rótulo.
- **Data API não vê `redirect_url` / `pagina` / UTM de evento** — só
  `customEvent:nome_painel` está registrado. Separar os fluxos exige registrar
  `redirect_url` como dimensão personalizada no GA4.
- **Decisão (2026-08-28)**: adiado. Não registrar as dimensões agora; Report B
  segue só com `nome_painel`. O ranking de painel fica **preliminar** (soma os
  dois eventos, separados por `event_name`) até haver semanas de dado limpo.
  Dashboard inicial foca no Report A (uso do site). Retomar com: registrar
  `redirect_url`+`pagina`, coluna `origem` ('relatorios'|'homepage'|'dupe') na
  silver, filtro de referrer p/ tirar teste.
- Grafias reais divergem dos alvos de normalização do readme:
  `Cotações - Preços de Referência` (readme: "Preços de Referência"),
  `Matrizes Tecnificadas - Modelo de Produção` (readme: "Matrizes Tecnificadas"),
  `Cotações - Insumos` (readme: "Insumos"), `Cenário Empresarial - Evolução`, `Tutorial`.

## Teste 4 — Diagnóstico de bots (dados atuais, ago/2026)
| País | Sessões | Engajadas | Taxa | Tempo méd. |
|---|---|---|---|---|
| China | 102.376 | 5 | 0,0% | 0,0s |
| Brasil | 3.469 | 1.915 | 55,2% | 36,2s |
| EUA | 255 | 101 | 39,6% | 6,3s |
| Japão | 157 | 13 | 8,3% | 0,4s |

- China = **~96% de todas as sessões**. Todo o tráfego-bot está no site **institucional** (`abcs.org.br`); `abcsdata` está limpo.
- **Os bots usam `browser = "Chrome"` e `operatingSystem = "Windows"`** — não vêm vazios. O filtro secundário do readme (`browser != ''`) não pega nada: só 25 sessões têm browser `(not set)`.
- Sinal robótico confiável no grão agregado: **`engagedSessions = 0` E `userEngagementDuration = 0`**.
- Japão/Vietnã/Bolívia etc. aparecem com engajamento real baixo mas > 0 — confirmam a decisão de **não filtrar por país**.

## Teste 5 — Extração simulada + profundidade histórica
- Grão completo (9 dim): **588 linhas/dia**. Cabe folgado em 1 chamada.
- **Onda de bots é recente**: baseline ~2.000–2.500 usuários/mês (2023 a abr/2026) → jun/2026: 16,8k → **jul/2026: 179k** → ago/2026: 106k. Dados antes de ~mai/2026 estão limpos.
- Linha-bot típica: `China | Kashgar Prefecture | desktop | Chrome | Windows | page_view | (not set) | 3175 sessões | 0 engajadas | 0s`.

### Achado crítico da carga histórica: `customEvent:nome_painel` corta o histórico
Um relatório que inclui a dimensão personalizada `customEvent:nome_painel`
**só retorna linhas a partir da criação da dimensão** (~jun/2026) — não retorna
`(not set)` para o passado, retorna zero. **Não é retenção de dados.**

| Consulta | Alcança |
|---|---|
| 8 dim, **sem** `nome_painel` | fev/2023 (3.692 linhas/mês) |
| 9 dim, **com** `nome_painel` | só jun/2026 em diante |
| eventos `painel_acessado`/`painel_clicado` de fato | ~120 eventos, quase todos ≥ 27/08/2026 |

→ **Dois relatórios / duas tabelas** (Report A site sem custom dim; Report B
painéis com custom dim, filtrado a eventos de painel).

---

## Consequências para o desenho (vs readme_previo)

1. **Filtro de bot**: coluna `trafego_valido` na Silver (filtrada na Gold), decidida **por segmento** (dia × host × geo × device × browser × OS) a partir da linha `session_start` e propagada aos demais eventos do segmento. Regra: vale se `engaged_sessions > 0` **e** não é blob de bot (`sessions >= 30 AND taxa_engajamento < 5%`). A onda da China aparece como 1 segmento/dia de ~3.000 sessões com 3 engajadas (0,09%) — excluído; segmentos pequenos com baixa taxa são preservados (usuários reais navegando de leve). Limiares heurísticos, revisar com mais histórico.
   - Descartado o filtro `browser != ''` do readme (inútil — bots são "Chrome"/"Windows").
   - Tempo de engajamento sozinho não serve: linhas de `user_engagement` da China têm tempo residual > 0 com 0 sessões engajadas.
   - Métricas de sessão/usuário (`sessions`, `engagedSessions`, `activeUsers`) **repetem em cada linha de `eventName`** no runReport → só podem ser somadas num recorte de 1 evento.
   - **Mas cada métrica tem seu evento de origem**: `sessions/engaged/users` são consistentes em `session_start`; `userEngagementDuration` só acumula em `user_engagement` (é ~0 em `session_start`/`page_view`/`first_visit`). `gold.vw_sessoes` faz `SUM(...) FILTER (WHERE event_name = <evento certo>)` por métrica. `userEngagementDuration` do runReport **já vem em segundos** — não há conversão de ms no Python (`load_bronze.py` não converte nada, só grava o JSON cru).
2. **`nome_painel`**: os 18 painéis do Data Insights são **todos distintos** (`Cenário Empresarial` ≠ `Cenário Empresarial - Evolução` etc.). O time mantém um CSV com a lista + classificação (tema, hierarquia, público); virou `sql/seed_dim_painel.sql` (`silver.dim_painel`). O GTM manda o nome canônico → **match exato** na Gold (`gold.vw_painel_normalizado`), com `silver.dim_painel_alias` para exceções/drift. `Comércio Exterior - Exportações/Importações` do CSV = 1 painel `Comércio Exterior`. `Tutorial` = `tipo='auxiliar'` (fora do ranking). CSV fica fora do git.
3. **Dois relatórios**: `bronze.ga4_site_raw` (Report A, fev/2023+) e
   `bronze.ga4_paineis_raw` (Report B, jun/2026+, filtrado a `painel_acessado`/
   `painel_clicado`). Silver: `silver.ga4_eventos` e `silver.ga4_paineis`.
   `controle_execucao` tem coluna `relatorio` ('site'|'painel').
   Grão geo: `country, region, city` (`region` = estado, GA4 devolve "State of ...").
4. **Bronze** = payload JSON cru append-only (1 linha/dia), não colunas tipadas.
5. **Silver** = "apaga o dia e reinsere" (idempotente), não `CREATE TABLE AS`.
6. **`ga4_paineis` sem `trafego_valido`**: abcsdata não tem onda de bots e a
   métrica é a contagem bruta de acessos por painel.
7. `painel_clicado` **entra no modelo** junto com `painel_acessado`.
8. Abrir tarefa no GTM: 48% de `nome_painel = (not set)`.
