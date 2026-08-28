"""
Teste 5 — Simular a consulta de extracao diaria real.

Roda o runReport no grao que a camada Bronze usaria (date, host, geo,
device, browser, OS, eventName, nome_painel) pra medir:
  - volume de linhas por dia (cabe na quota? precisa paginar?)
  - se as metricas do modelo existem e retornam
  - profundidade historica disponivel (desde quando ha dados)

Rodar:  python testes/05_extracao_simulada.py
"""

import sys

from _ga4 import run_report, rows_to_tuples

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

DIMS = [
    "date", "hostName", "country", "city", "deviceCategory",
    "browser", "operatingSystem", "eventName", "customEvent:nome_painel",
]
METS = ["eventCount", "sessions", "engagedSessions", "activeUsers", "userEngagementDuration"]


def extrai(inicio, fim, limit=100000):
    payload = {
        "dateRanges": [{"startDate": inicio, "endDate": fim}],
        "dimensions": [{"name": d} for d in DIMS],
        "metrics": [{"name": m} for m in METS],
        "limit": limit,
    }
    return run_report(payload)


if __name__ == "__main__":
    print("=== 1) Grao completo, 1 dia (ontem) ===")
    r = extrai("yesterday", "yesterday")
    print(f"  rowCount API: {r.get('rowCount')}  | linhas no payload: {len(r.get('rows', []))}")
    print(f"  quota consumida: {r.get('propertyQuota')}")

    print("\n=== 2) Grao completo, ultimos 7 dias ===")
    r = extrai("7daysAgo", "yesterday")
    print(f"  rowCount API: {r.get('rowCount')}  | linhas no payload: {len(r.get('rows', []))}")

    print("\n=== 3) Profundidade historica (activeUsers por mes) ===")
    r = run_report({
        "dateRanges": [{"startDate": "2020-01-01", "endDate": "today"}],
        "dimensions": [{"name": "yearMonth"}],
        "metrics": [{"name": "activeUsers"}, {"name": "sessions"}],
        "limit": 200,
    })
    for ym, us, ses in sorted(rows_to_tuples(r)):
        print(f"  {ym}: {us:>8} usuarios | {ses:>8} sessoes")

    print("\n=== 4) Amostra do grao completo (10 primeiras linhas de ontem) ===")
    r = extrai("yesterday", "yesterday", limit=10)
    for t in rows_to_tuples(r):
        print("  " + " | ".join(t))
