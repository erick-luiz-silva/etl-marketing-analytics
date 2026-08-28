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
- Existe também um evento **`painel_clicado`** (42 eventos) não citado no readme.
- Só `abcsdata.abcs.org.br` gera `painel_acessado` (esperado).
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

## Teste 5 — Extração simulada (grão completo)
- Grão: `date, hostName, country, city, deviceCategory, browser, operatingSystem, eventName, customEvent:nome_painel`.
- Volume: **588 linhas/dia**, 2.821 linhas/7 dias. Cabe folgado em 1 chamada, sem paginação.
- Profundidade histórica: dados desde **fev/2023**.
- **Onda de bots é recente**: baseline ~2.000–2.500 usuários/mês (2023 a abr/2026) → jun/2026: 16,8k → **jul/2026: 179k** → ago/2026: 106k. Dados antes de ~mai/2026 estão limpos.
- Linha-bot típica: `China | Kashgar Prefecture | desktop | Chrome | Windows | page_view | (not set) | 3175 sessões | 0 engajadas | 0s`.

---

## Consequências para o desenho (vs readme_previo)

1. **Filtro de bot**: coluna `trafego_valido` na Silver (filtrada na Gold), decidida **por segmento** (dia × host × geo × device × browser × OS) a partir da linha `session_start` e propagada aos demais eventos do segmento. Regra: vale se `engaged_sessions > 0` **e** não é blob de bot (`sessions >= 30 AND taxa_engajamento < 5%`). A onda da China aparece como 1 segmento/dia de ~3.000 sessões com 3 engajadas (0,09%) — excluído; segmentos pequenos com baixa taxa são preservados (usuários reais navegando de leve). Limiares heurísticos, revisar com mais histórico.
   - Descartado o filtro `browser != ''` do readme (inútil — bots são "Chrome"/"Windows").
   - Tempo de engajamento sozinho não serve: linhas de `user_engagement` da China têm tempo residual > 0 com 0 sessões engajadas.
   - Métricas de sessão/usuário (`sessions`, `engagedSessions`, `activeUsers`) **repetem em cada linha de `eventName`** no runReport → só podem ser somadas num recorte de 1 evento. Gold usa `gold.vw_sessoes` (recorte `session_start`) para essas métricas.
2. **`nome_painel`**: os 18 painéis do Data Insights são **todos distintos** (`Cenário Empresarial` ≠ `Cenário Empresarial - Evolução` etc.). O time mantém um CSV com a lista + classificação (tema, hierarquia, público); virou `sql/seed_dim_painel.sql` (`silver.dim_painel`). O GTM manda o nome canônico → **match exato** na Gold (`gold.vw_painel_normalizado`), com `silver.dim_painel_alias` para exceções/drift. `Comércio Exterior - Exportações/Importações` do CSV = 1 painel `Comércio Exterior`. `Tutorial` = `tipo='auxiliar'` (fora do ranking). CSV fica fora do git.
3. **Bronze** = payload JSON cru append-only + `data_extracao` (padrão proposições), não colunas tipadas.
4. **Silver** = tabela fixa + `INSERT ... ON CONFLICT` idempotente, não `CREATE TABLE AS`.
5. **Tabela de controle** de janela incremental (equivalente a `bronze.controle_execucao`).
6. **Carga histórica**: métricas de site desde fev/2023; análise de painel só desde 27/08/2026.
7. Incluir o evento **`painel_clicado`** no escopo (decidir se entra no modelo).
8. Abrir tarefa no GTM: 48% de `nome_painel = (not set)`.
