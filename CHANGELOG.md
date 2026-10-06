# Registro de mudanças

Mudanças relevantes de dados, modelo e entregáveis — o que mudou, por quê e o que
fazer para aplicar. Detalhes de investigação ficam em `testes/ACHADOS.md`.

## 2026-10-06

### Painéis contados pela URL da página (Report D)
- **O quê:** nova extração dos page_views `/relatorios/?redirect=` por data × URL,
  com aberturas, pessoas no dia e pessoas únicas em 7/28 dias. O ID do relatório
  Power BI é decodificado da URL (`silver.fn_alvo_redirect`) e mapeado para o
  painel em `silver.dim_painel_relatorio` (com a versão desktop/mobile) →
  `gold.vw_paineis_acessos`. Auditoria de IDs novos: `gold.vw_paineis_url_sem_mapa`.
- **Por quê:** o evento de clique (`painel_acessado`) parou de disparar de ~19/09 a
  05/10 quando o site mudou o menu. A URL não depende de tag de clique.
- **Relatório semanal:** ranking de painéis passa a mostrar **acessos** (pessoa ×
  painel × dia) e **pessoas** (únicas na semana). O aviso de "dados de painel em
  consolidação" saiu.
- **Impacto nos números:** semana 28/09–04/10: 151 acessos (antes: 20 cliques).
  O ranking muda de ordem (SIF Abate e IBGE Abate sobem).
- **Atenção:** antes de ~15/09 a contagem por URL é um piso (o menu trocava o
  painel sem recarregar a página). Para esse período o evento de clique
  (`gold.vw_paineis_ranking`) é mais completo.
- **Dimensão:** `Competitividade Carne Suína` (COTAÇÕES/PREÇOS) e `Mercado Global`
  (COMÉRCIO EXTERIOR) entram na `dim_painel`; ordem de menu e público a definir.
- **Aplicar:** `python src/setup_db.py`, `python src/load_dimensoes.py`,
  `python src/extract_bronze.py --relatorios paginas`.

## 2026-10-05

### Validação contra o export BigQuery + aliases de painéis
- **O quê:** silver conferida contra o export bruto do GA4 no BigQuery
  (27/08–03/10). 25 aliases novos em `sql/seed_dim_painel.sql` (grafias sem
  hífen, rótulo-folha, traduções es/fr e os nomes do GTM v10 para Comércio Exterior).
- **Resultado:** eventos batem 100% (dia × host × evento); sessões ±0,3%; DAU ±1,4%.
  Painéis batem exatamente a partir de 28/08 (27/08 tem `(not set)` a mais na Data API).
- **Impacto nos números:** 59 eventos de painel que estavam em
  `gold.vw_paineis_sem_mapeamento` passam a contar no ranking (de 70 para 11 sem mapeamento).
- **Atenção:** 11% dos `painel_acessado` são Preview do GTM (`debug_mode`), contados
  como acesso. `Competitividade Carne Suína` e `Mercado Global` ainda não estão na dim.
- **Aplicar:** `python src/load_dimensoes.py` (já aplicado no banco em 2026-10-05).

### Usuários ativos: DAU / WAU / MAU (Report C)
- **O quê:** nova extração GA4 com `active1DayUsers` / `active7DayUsers` /
  `active28DayUsers` por data × host × país × dispositivo →
  `bronze.ga4_usuarios_raw` → `silver.ga4_usuarios` → `gold.vw_usuarios_ativos`.
- **Por quê:** usuário não é aditivo; a soma de `activeUsers` entre dias inflava os
  "usuários da semana". WAU = semana seg–dom; MAU = 28 dias móveis.
- **Impacto nos números:** DAU fica maior que a soma antiga de usuários válidos
  (não descarta mais usuário real que não engajou); WAU/MAU passam a existir.
- **Aplicar:** `python setup_db.py` e depois `python extract_bronze.py --relatorios usuarios`.

### Relatório semanal: usuários e médias
- **O quê:** PDF e texto do WhatsApp passam a mostrar, por portal, usuários na
  semana (WAU), usuários por dia (média), usuários no mês (MAU 28 dias), visitas por
  dia, visitas por usuário e tempo médio por visita. Sai o bloco de bots/tráfego
  bruto e o card PNG. Ranking de painéis só com `painel_acessado`.
- **Trava:** o script recusa gerar se o domingo não está completo na base
  (`--forcar` ignora). O resumo de 14–20/09 tinha saído com dados só até 18/09.
- **Impacto nos números — atenção na comparação com relatórios antigos:**
  - "Visitas" ≠ "sessões reais" antigas: agora saem do mesmo recorte dos usuários
    e incluem visitas reais sem engajamento. Ex. 28/09–04/10, Data Insights:
    189 visitas (critério antigo: 93). A variação semanal passa a ser de usuários (WAU).
  - "Usuários" antigos eram soma de usuários diários (inflada); WAU conta cada pessoa uma vez.

### Hosts fora da ABCS deixam de contar como Institucional
- **O quê:** `silver.fn_site()` com lista explícita de hosts; o resto vira `'Outros'`
  e sai da gold (inclui `localhost` dos testes de painel).
- **Impacto:** ~300 sessões históricas a menos no Institucional (2023–24).
- **Aplicar:** `python load_silver.py --completo` (uma vez).

### Silver incremental
- **O quê:** a transformação reprocessa só os dias com snapshot novo na bronze
  (antes: o histórico inteiro, todo dia). `--completo` força tudo.

### PBIP versionado
- `BI/` entra no git (Report + SemanticModel). Fora: `.pbix`, `cache.abf`,
  `.pbi/localSettings.json`.
