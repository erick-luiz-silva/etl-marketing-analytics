"""
Teste 1 — Autenticacao via Service Account.

Reproduz o runReport basico do teste original, mas com credenciais de
Service Account (config/credentials.json) em vez de access_token manual:
sem expiracao, sem intervencao.

Rodar:  python testes/01_auth.py
"""

from _ga4 import run_report, rows_to_tuples

if __name__ == "__main__":
    r = run_report({
        "metrics": [{"name": "activeUsers"}],
        "dimensions": [{"name": "date"}],
        "dateRanges": [{"startDate": "7daysAgo", "endDate": "today"}],
    })
    linhas = sorted(rows_to_tuples(r))
    print(f"{len(linhas)} linhas:\n")
    for data, usuarios in linhas:
        print(f"  {data}: {usuarios} usuarios ativos")
    print("\nOK - Service Account autentica e le a propriedade.")
