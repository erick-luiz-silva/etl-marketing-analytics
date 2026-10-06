"""
Teste 9 — Aberturas de painel pela URL da página (Report D).

O ranking de painéis dependia do evento painel_acessado (tag de clique no GTM),
que parou de disparar em ~19/09/2026 quando o site trocou o menu para
abrirPainel(). Mas toda abertura de painel carrega /relatorios/?redirect=<URL do
Power BI>, e o parâmetro r= da URL é um JSON em base64 com o ID do relatório
("k"). Contar page_views por ID não depende de tag de clique.

Perguntas:
  1. Todas as URLs de painel decodificam para um ID (ou tutorial/contato)?
  2. Quantos IDs não estão no mapa (sql/seed_dim_painel.sql)?
  3. Até onde vai o histórico? Com quais dimensões?
  4. Quanto o evento de clique perdeu frente às aberturas, por semana?

Rodar:  python testes/09_paineis_pagelocation.py [inicio] [fim]
"""

import base64
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

from _ga4 import get_token, run_report, rows_to_tuples

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

INICIO = sys.argv[1] if len(sys.argv) > 1 else "2026-06-01"
FIM = sys.argv[2] if len(sys.argv) > 2 else "yesterday"
SEED = Path(__file__).resolve().parent.parent / "sql" / "seed_dim_painel.sql"
TOKEN = get_token()

FILTRO_HOST = {"filter": {"fieldName": "hostName",
                          "stringFilter": {"value": "abcsdata.abcs.org.br"}}}


def filtro(evento, url_contem=None):
    exprs = [FILTRO_HOST, {"filter": {"fieldName": "eventName",
                                      "stringFilter": {"value": evento}}}]
    if url_contem:
        exprs.append({"filter": {"fieldName": "pageLocation",
                                 "stringFilter": {"matchType": "CONTAINS", "value": url_contem}}})
    return {"andGroup": {"expressions": exprs}}


def rel(dims, mets, dim_filter):
    r = run_report({
        "dateRanges": [{"startDate": INICIO, "endDate": FIM}],
        "dimensions": [{"name": d} for d in dims],
        "metrics": [{"name": m} for m in mets],
        "dimensionFilter": dim_filter,
        "limit": 100000,
    }, TOKEN)
    return rows_to_tuples(r)


def alvo(url):
    """Mesma lógica de silver.fn_alvo_redirect."""
    u = unquote(unquote(url))
    m = re.search(r"[?&]r=([A-Za-z0-9+/_-]+)", u)
    if not m:
        m = re.search(r"redirect=([^&#?]+)", u)
        return m.group(1) if m else None
    b = m.group(1).replace("-", "+").replace("_", "/")
    b += "=" * (-len(b) % 4)
    try:
        return json.loads(base64.b64decode(b))["k"]
    except Exception:
        return None


def semana(d):
    dt = datetime.strptime(d, "%Y%m%d").date()
    return date.fromordinal(dt.toordinal() - dt.weekday())


if __name__ == "__main__":
    mapa = dict(re.findall(r"\('([0-9a-f-]{36}|[a-z]+\.php)',\s+'([^']+)'", SEED.read_text("utf-8")))
    print(f"Período {INICIO} → {FIM}; {len(mapa)} alvos no mapa do seed\n")

    # 1/2. decodificação e cobertura do mapa
    linhas = rel(["date", "pageLocation"], ["eventCount"], filtro("page_view", "redirect="))
    por_alvo, sem_alvo = defaultdict(int), 0
    aberturas_sem = defaultdict(int)
    for d, url, n in linhas:
        a = alvo(url)
        if a is None:
            sem_alvo += int(n)
            continue
        por_alvo[a] += int(n)
        if a in mapa:
            aberturas_sem[semana(d)] += int(n)
    total = sum(por_alvo.values()) + sem_alvo
    print(f"1) page_views de painel: {total}; sem alvo decodificável: {sem_alvo}")
    fora = {a: n for a, n in por_alvo.items() if a not in mapa}
    print(f"2) alvos fora do mapa: {fora or 'nenhum'}\n")

    # 3. histórico: a combinação pageLocation + deviceCategory é cortada pela retenção
    for dims in (["yearMonth", "pageLocation"], ["yearMonth", "pageLocation", "deviceCategory"]):
        meses = defaultdict(int)
        for t in rel(dims, ["eventCount"], filtro("page_view", "redirect=")):
            meses[t[0]] += int(t[-1])
        print(f"3) {' × '.join(dims):40} {dict(sorted(meses.items()))}")

    # 4. evento de clique × aberturas pela URL
    clique = defaultdict(int)
    for d, n in rel(["date"], ["eventCount"], filtro("painel_acessado")):
        clique[semana(d)] += int(n)
    print("\n4) semana       aberturas_url  painel_acessado  razão")
    for s in sorted(set(aberturas_sem) | set(clique)):
        ab, cl = aberturas_sem.get(s, 0), clique.get(s, 0)
        print(f"   {s}  {ab:>12}  {cl:>15}  {cl / ab if ab else 0:>5.2f}")
