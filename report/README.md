# Relatório semanal + resumo para WhatsApp

Gera, a partir das views `gold` do Postgres, o que vai para o time toda segunda:
- **Relatório completo**: `abcs_weekly_onepage_v2.html` / `.pdf` (A4, 1 página).
- **Resumo**: `resumo_semana.txt` — texto formatado para WhatsApp, ponto de partida
  para o texto final (ajustado à mão antes de enviar).

```powershell
# semana fechada mais recente (segunda→domingo)
python report/gerar_relatorio.py

# uma semana específica (informe o domingo)
python report/gerar_relatorio.py --fim 2026-08-31

# só o relatório completo / só o texto
python report/gerar_relatorio.py --no-resumo
python report/gerar_relatorio.py --no-pdf

# gerar mesmo com a semana incompleta na base (ver abaixo)
python report/gerar_relatorio.py --forcar
```

O PDF é gerado por Chrome/Edge headless. Se nenhum dos dois estiver instalado, o
script avisa e pula essa etapa (o HTML/txt ainda saem).

## Trava de semana incompleta

Antes de gerar, o script confere se a base tem o **domingo** da semana em
`silver.ga4_eventos` e `silver.ga4_usuarios`, e se ele foi extraído **depois do
meio-dia de segunda** (a GA4 só fecha o dia D por volta do meio-dia de D+1 —
`testes/ACHADOS.md`, teste 6). Se não, para com a lista do que falta.

Motivo: o resumo de 14–20/09 saiu com dados só até 18/09 (o agendador não rodou
no fim de semana) e mostrou painéis e Institucional bem abaixo do real.

Fluxo da segunda: `python src/pipeline.py` (se a tarefa das 17h ainda não rodou)
→ `python report/gerar_relatorio.py`.

## Indicadores

Tudo por portal, comparando com a semana anterior. Usuários, visitas, engajamento
e tempo vêm de `gold.vw_usuarios_ativos`, no mesmo recorte de tráfego válido —
por isso as razões fecham (visitas por usuário ≥ 1).

| Indicador | Definição |
|---|---|
| Usuários na semana (WAU) | usuários únicos seg–dom (`wau` do domingo) — base do TL;DR e da variação |
| Usuários por dia | média dos 7 `dau` diários |
| Usuários no mês (MAU) | usuários únicos dos 28 dias até o domingo (`mau`) |
| Visitas por dia | `sessoes_7d` do domingo ÷ 7 |
| Visitas por usuário | `sessoes_7d` ÷ WAU |
| Tempo médio por visita | `tempo_engajamento_7d_s` ÷ `sessoes_7d` |
| % visitas engajadas | `sessoes_engajadas_7d` ÷ `sessoes_7d` |
| Top países | usuários (WAU) por país |
| Top estados | visitas por estado (`gold.vw_site_overview`, só Brasil) |
| Dispositivos (Data Insights) | usuários (WAU) por dispositivo |
| Usuários por dia (Data Insights) | `dau` de cada dia da semana |
| Ranking de painéis | `gold.vw_paineis_ranking`, **só `painel_acessado`** (somar `painel_clicado` contaria o mesmo acesso duas vezes) |

Tráfego robótico já vem descontado nas views e **não aparece** no relatório nem no
texto; o acompanhamento de bots fica no Power BI (página de qualidade).

O TL;DR só destaca um portal se o WAU variar **≥ 10%**; se os dois ficarem
estáveis, diz isso em vez de forçar números. Mesma lógica (`construir_tldr`,
`frase_delta`) no PDF e no texto.

## Arquivos

| | |
|---|---|
| `template_weekly.html` | modelo do relatório (marcadores `{{...}}`, paleta ABCS) — versionado |
| `gerar_relatorio.py` | consulta o banco uma vez (`coletar_dados`) e gera os entregáveis |
| `logo_abcs_png/` | logos ABCS; o script embute `ABCS-Horizontal-1.png` como data URI — versionado |
| `abcs_weekly_onepage_v2.html` / `.pdf`, `resumo_semana.txt` | **saídas**, sobrescritas a cada execução (fora do git) |

## Observações

- Painéis: números baixos e preliminares até o rastreamento estabilizar — o
  relatório sinaliza isso nas primeiras semanas após 27/08/2026.
- O card PNG para WhatsApp foi removido em 05/10/2026 (não era usado).
