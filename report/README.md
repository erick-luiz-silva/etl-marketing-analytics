# Relatório semanal + resumo para WhatsApp

Gera, a partir das views `gold` do Postgres:
- **Relatório completo**: `abcs_weekly_onepage_v2.html` / `.pdf` (A4, 1 página) — para leitura detalhada.
- **Resumo executivo**: `resumo_semana.txt` (texto formatado p/ WhatsApp) + `resumo_semana.png` (card/print) — para encaminhar direto para a alta gestão.

```powershell
# semana fechada mais recente (segunda→domingo) — gera os 4 arquivos
python report/gerar_relatorio.py

# uma semana específica (informe o domingo)
python report/gerar_relatorio.py --fim 2026-08-31

# só o relatório completo (sem o resumo)
python report/gerar_relatorio.py --no-resumo

# só o resumo (sem o PDF do relatório)
python report/gerar_relatorio.py --no-pdf

# nomes de saída customizados
python report/gerar_relatorio.py --saida report/semana.html --resumo-txt report/msg.txt --resumo-png report/card.png
```

PDF e PNG são gerados por Chrome/Edge headless. Se nenhum dos dois estiver
instalado, o script avisa e pula essa etapa (o HTML/txt ainda saem).

## Arquivos

| | |
|---|---|
| `template_weekly.html` | modelo do relatório completo (marcadores `{{...}}`, paleta ABCS). |
| `template_resumo.html` | modelo do card de resumo (1080×1040, mesmo estilo de marcadores). |
| `gerar_relatorio.py` | consulta o banco uma vez (`coletar_dados`), gera os 4 entregáveis a partir dos mesmos dados. |
| `abcs_weekly_onepage_v2.html` / `.pdf` | **saída** — relatório completo (sobrescrita a cada execução). |
| `resumo_semana.txt` | **saída** — mensagem pronta pra colar no WhatsApp (`*negrito*`, emoji, leitura de ~15s). |
| `resumo_semana.png` | **saída** — card verde ABCS com os mesmos números, pra enviar como imagem. |
| `logo_abcs_png/` | logos ABCS. O script embute `ABCS-Horizontal-1.png` como data URI. |

## Como o resumo é redigido

`gerar_relatorio.py` monta um TL;DR automático comparando a semana com a
anterior: só destaca um portal se a variação for **≥ 10%** ("Data Insights
caiu 17%..."); se os dois ficarem estáveis, diz isso em vez de forçar números.
Sempre inclui: sessões reais e % engajado de cada portal, o **top 3 painéis**
da semana (desempate estável: acessos → sessões engajadas → nome), e o % de
tráfego bot removido. Mesma lógica (`construir_tldr`, `frase_delta`,
`paineis_top3_html`) usada no texto e no card — não são dois textos escritos à mão.

## Medidas

Espelham `BI/info_medidas.csv` (mesmas fórmulas, em SQL):

- **Sessões / Visitantes / Sessões engajadas / Tempo médio** por portal → `gold.vw_site_overview` (já filtra `trafego_valido`).
- **Top países / estados** → `gold.vw_site_overview` agregado por `country` / `region` (estado só Brasil, prefixo "State of " removido).
- **Dispositivos (Data Insights)** → `gold.vw_site_overview` por `device_category`.
- **Ranking de painéis / categoria** → `gold.vw_paineis_ranking` (soma `painel_acessado` + `painel_clicado` — **preliminar**, ver `testes/ACHADOS.md`).
- **Qualidade / % bots** → `gold.vw_qualidade_trafego`.

## Observações

- A semana padrão é a última **segunda→domingo** já encerrada. Rodar na
  segunda ou terça pode pegar o domingo ainda incompleto (defesa: a carga
  incremental recobre D-3, então rodar 2+ dias depois já está estável).
- Painéis: números baixos e preliminares até o rastreamento estabilizar —
  tanto o relatório quanto o resumo sinalizam isso quando é o caso.
- Os `.html`/`.pdf`/`.txt`/`.png` de saída são derivados, não precisam ir pro
  git. Versionar `template_weekly.html`, `template_resumo.html` e `gerar_relatorio.py`.
