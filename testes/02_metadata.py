"""
Teste 2 — Metadata da propriedade.

Objetivo: descobrir o nome EXATO da dimensão personalizada de painel
(customEvent:nome_painel? outra grafia?) e listar todas as dimensões/
métricas custom registradas, além de confirmar que as dimensões que o
readme_previo pressupõe (hostName, sessionEngaged, browser, deviceCategory,
country, city) existem na API.

Rodar:  python testes/02_metadata.py
"""

from _ga4 import get_metadata

ESPERADAS = [
    "hostName", "sessionEngaged", "browser", "deviceCategory",
    "country", "city", "eventName",
]

if __name__ == "__main__":
    meta = get_metadata()

    dims = meta.get("dimensions", [])
    mets = meta.get("metrics", [])
    print(f"{len(dims)} dimensoes, {len(mets)} metricas disponiveis na propriedade\n")

    print("=== Dimensoes personalizadas (customEvent: / customUser:) ===")
    for d in dims:
        api_name = d["apiName"]
        if api_name.startswith("custom") or "custom" in api_name.lower():
            print(f"  {api_name:45} | {d.get('uiName')}")

    print("\n=== Metricas personalizadas ===")
    for m in mets:
        if m["apiName"].startswith("custom"):
            print(f"  {m['apiName']:45} | {m.get('uiName')}")

    print("\n=== Qualquer coisa com 'painel' no nome ===")
    for d in dims:
        blob = f"{d['apiName']} {d.get('uiName','')} {d.get('description','')}".lower()
        if "painel" in blob or "relatorio" in blob or "relatório" in blob:
            print(f"  DIM {d['apiName']:40} | {d.get('uiName')} | {d.get('description','')[:60]}")

    print("\n=== Dimensoes esperadas pelo readme_previo ===")
    nomes = {d["apiName"] for d in dims}
    for e in ESPERADAS:
        print(f"  {'OK ' if e in nomes else 'FALTA'} {e}")
