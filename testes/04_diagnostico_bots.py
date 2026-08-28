"""
Teste 4 — Revalidar o diagnostico de bots contra os dados atuais.

IMPORTANTE: a GA4 Data API NAO tem a dimensao `sessionEngaged` (isso so
existe no export BigQuery). O filtro primario do readme_previo
(`session_engaged = '1'`) precisa ser repensado. Aqui medimos os sinais
que a Data API oferece de fato: sessions vs engagedSessions, engagementRate,
userEngagementDuration, quebrados por country / browser / OS.

Rodar:  python testes/04_diagnostico_bots.py
"""

import sys

from _ga4 import run_report, rows_to_tuples

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

INICIO = "2026-08-01"
FIM = "today"


def rel(dims, mets, limit=50):
    return run_report({
        "dateRanges": [{"startDate": INICIO, "endDate": FIM}],
        "dimensions": [{"name": d} for d in dims],
        "metrics": [{"name": m} for m in mets],
        "limit": limit,
        "orderBys": [{"metric": {"metricName": mets[0]}, "desc": True}],
    })


METRICAS = ["sessions", "engagedSessions", "engagementRate", "userEngagementDuration", "eventCount"]


def mostra(titulo, dims):
    print(f"\n=== {titulo} ===")
    r = rel(dims, METRICAS)
    header = " | ".join(dims) + "  ->  ses / eng / taxa / tempo_s / eventos"
    print(header)
    for t in rows_to_tuples(r):
        d = t[:len(dims)]
        ses, eng, taxa, tempo, ev = t[len(dims):]
        taxa_pct = f"{float(taxa)*100:.1f}%"
        tempo_med = float(tempo) / int(ses) if int(ses) else 0
        print(f"  {' | '.join(d):40} {ses:>7} / {eng:>6} / {taxa_pct:>6} / {tempo_med:6.1f} / {ev}")


if __name__ == "__main__":
    mostra("Por pais", ["country"])
    mostra("Por browser", ["browser"])
    mostra("Por sistema operacional", ["operatingSystem"])
    mostra("Pais x browser (top)", ["country", "browser"])
    mostra("hostName x pais", ["hostName", "country"])
