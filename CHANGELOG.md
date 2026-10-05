# Registro de mudanças

Mudanças relevantes de dados, modelo e entregáveis — o que mudou, por quê e o que
fazer para aplicar. Detalhes de investigação ficam em `testes/ACHADOS.md`.

## 2026-10-05

### Usuários ativos: DAU / WAU / MAU (Report C)
- **O quê:** nova extração GA4 com `active1DayUsers` / `active7DayUsers` /
  `active28DayUsers` por data × host × país × dispositivo →
  `bronze.ga4_usuarios_raw` → `silver.ga4_usuarios` → `gold.vw_usuarios_ativos`.
- **Por quê:** usuário não é aditivo; a soma de `activeUsers` entre dias inflava os
  "usuários da semana". WAU = semana seg–dom; MAU = 28 dias móveis.
- **Impacto nos números:** DAU fica maior que a soma antiga de usuários válidos
  (não descarta mais usuário real que não engajou); WAU/MAU passam a existir.
- **Aplicar:** `python setup_db.py` e depois `python extract_bronze.py --relatorios usuarios`.

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
