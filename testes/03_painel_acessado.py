"""
Teste 3 — Evento painel_acessado + dimensao customEvent:nome_painel.

Objetivo: confirmar que ha dados desde 27/08/2026 (ativacao da tag) e ver
as grafias reais de nome_painel que vao alimentar a normalizacao.
Tambem quebra por hostName pra ver se os dois portais aparecem.

Rodar:  python testes/03_painel_acessado.py
"""

from _ga4 import run_report, rows_to_tuples

INICIO = "2026-08-27"
FIM = "today"


def relatorio(dimensions, metrics, dimension_filter=None, limit=100):
    payload = {
        "dateRanges": [{"startDate": INICIO, "endDate": FIM}],
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
        "limit": limit,
    }
    if dimension_filter:
        payload["dimensionFilter"] = dimension_filter
    return run_report(payload)


FILTRO_PAINEL = {
    "filter": {"fieldName": "eventName", "stringFilter": {"value": "painel_acessado"}}
}

if __name__ == "__main__":
    print("=== 1) Volume diario do evento painel_acessado ===")
    r = relatorio(["date"], ["eventCount", "sessions", "activeUsers"], FILTRO_PAINEL)
    linhas = sorted(rows_to_tuples(r))
    if not linhas:
        print("  NENHUMA linha — evento nao existe ou sem dados no periodo")
    for data, ev, ses, us in linhas:
        print(f"  {data}: {ev} eventos | {ses} sessoes | {us} usuarios")

    print("\n=== 2) painel_acessado por nome_painel (grafias reais) ===")
    r = relatorio(
        ["customEvent:nome_painel"],
        ["eventCount", "activeUsers"],
        FILTRO_PAINEL,
    )
    linhas = sorted(rows_to_tuples(r), key=lambda t: -int(t[1]))
    for nome, ev, us in linhas:
        print(f"  {ev:>6} ev | {us:>4} us | {nome!r}")

    print("\n=== 3) painel_acessado por hostName ===")
    r = relatorio(["hostName"], ["eventCount"], FILTRO_PAINEL)
    for host, ev in sorted(rows_to_tuples(r), key=lambda t: -int(t[1])):
        print(f"  {ev:>6} | {host}")

    print("\n=== 4) Todos os eventName no periodo (contexto) ===")
    r = relatorio(["eventName"], ["eventCount"])
    for nome, ev in sorted(rows_to_tuples(r), key=lambda t: -int(t[1])):
        print(f"  {ev:>8} | {nome}")
