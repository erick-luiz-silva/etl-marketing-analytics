"""
Teste 7 — Usuários ativos (DAU / WAU / MAU) pela Data API.

Usuário não é aditivo: somar activeUsers de vários dias ou segmentos conta a
mesma pessoa mais de uma vez. A Data API tem métricas de janela móvel que
resolvem isso — active1DayUsers / active7DayUsers / active28DayUsers — cada uma
com os usuários únicos dos últimos 1 / 7 / 28 dias terminando em `date`.

Perguntas:
  1. As métricas active*DayUsers funcionam com a dimensão date?
  2. active7DayUsers no domingo == activeUsers da semana seg–dom (WAU fechado)?
  3. Quanto a soma por segmento (grão do Report A, p/ reaproveitar o filtro
     de bot) infla em relação ao total exato por host?
  4. Quanto sobra depois de tirar os segmentos robóticos?

Rodar:  python testes/07_usuarios_ativos.py [domingo ISO]
"""

import sys
from collections import defaultdict
from datetime import date, timedelta

from _ga4 import get_token, run_report, rows_to_tuples

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

hoje = date.today()
DOMINGO = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else hoje - timedelta(days=hoje.weekday() + 1)
SEGUNDA = DOMINGO - timedelta(days=6)

ROLLING = ["active1DayUsers", "active7DayUsers", "active28DayUsers"]
SEGMENTO = ["hostName", "country", "region", "city", "deviceCategory", "browser", "operatingSystem"]
TOKEN = get_token()


def rel(dims, mets, inicio, fim):
    out, offset = [], 0
    while True:
        r = run_report({
            "dateRanges": [{"startDate": inicio.isoformat(), "endDate": fim.isoformat()}],
            "dimensions": [{"name": d} for d in dims],
            "metrics": [{"name": m} for m in mets],
            "limit": 100000,
            "offset": offset,
        }, TOKEN)
        out += rows_to_tuples(r)
        offset += 100000
        if offset >= int(r.get("rowCount", 0)):
            return out


def site(host):
    return "Data Insights" if "abcsdata" in host else "Institucional"


def robotico(ses, eng):
    return eng == 0 or (ses >= 30 and eng / ses < 0.05)


if __name__ == "__main__":
    print(f"Semana de referência: {SEGUNDA} a {DOMINGO}\n")

    # --- 1. exato por host, por dia -------------------------------------------
    exato = defaultdict(lambda: [0, 0, 0])
    for host, d, a1, a7, a28 in rel(["hostName", "date"], ROLLING, SEGUNDA, DOMINGO):
        e = exato[(site(host), d)]
        for i, v in enumerate((a1, a7, a28)):
            e[i] += int(v)
    print("1) Exato por site (sem quebra) — DAU / WAU(7d) / MAU(28d):")
    for (s, d), (a1, a7, a28) in sorted(exato.items()):
        print(f"   {s:14} {d}  {a1:>6} {a7:>7} {a28:>7}")

    # --- 2. WAU fechado seg–dom vs active7DayUsers no domingo -----------------
    print("\n2) WAU fechado (activeUsers no intervalo seg–dom) vs active7DayUsers no domingo:")
    dom = DOMINGO.strftime("%Y%m%d")
    wau_fech = defaultdict(int)
    for host, u in rel(["hostName"], ["activeUsers"], SEGUNDA, DOMINGO):
        wau_fech[site(host)] += int(u)
    for s, u in sorted(wau_fech.items()):
        print(f"   {s:14} fechado={u:>6}  rolling7={exato[(s, dom)][1]:>6}")

    # --- 3/4. soma por segmento (grão do Report A) -----------------------------
    mets = ROLLING + ["sessions", "engagedSessions"]
    linhas = rel(["date"] + SEGMENTO, mets, SEGUNDA, DOMINGO)
    soma = defaultdict(lambda: [0, 0, 0])
    valido = defaultdict(lambda: [0, 0, 0])
    sem_sessao = 0
    for t in linhas:
        d, host = t[0], t[1]
        a1, a7, a28, ses, eng = (int(float(x)) for x in t[-5:])
        sem_sessao += ses == 0
        for i, v in enumerate((a1, a7, a28)):
            soma[(site(host), d)][i] += v
            if not robotico(ses, eng):
                valido[(site(host), d)][i] += v
    print(f"\n3/4) Grão de segmento: {len(linhas)} linhas na semana, {sem_sessao} com sessions=0")
    print("   site           data       métrica   exato  soma_seg  infla   válido")
    for (s, d) in sorted(exato):
        if d != dom:
            continue
        for i, nome in enumerate(["DAU", "WAU", "MAU"]):
            ex, sm, va = exato[(s, d)][i], soma[(s, d)][i], valido[(s, d)][i]
            infla = f"{(sm / ex - 1) * 100:+.1f}%" if ex else "-"
            print(f"   {s:14} {d}  {nome:7} {ex:>7} {sm:>9} {infla:>7} {va:>8}")

    # --- 5. grão grosso + filtro de bot calculado na JANELA --------------------
    # Alternativa ao grão de segmento: rolling metrics num grão em que um mesmo
    # usuário raramente muda de linha (host × país [× dispositivo]); o segmento é
    # robótico se, somando sessões da janela inteira (1/7/28 dias), cair na regra.
    print("\n5) Grão grosso, regra de bot sobre as sessões da janela (domingo):")
    janelas = {0: 1, 1: 7, 2: 28}
    for grao in (["hostName", "country"], ["hostName", "country", "deviceCategory"]):
        rolling = {tuple(t[:len(grao)]): [int(x) for x in t[len(grao):]]
                   for t in rel(grao, ROLLING, DOMINGO, DOMINGO)}
        print(f"   grão {' × '.join(grao)}  ({len(rolling)} linhas)")
        for i, nome in enumerate(["DAU", "WAU", "MAU"]):
            ini = DOMINGO - timedelta(days=janelas[i] - 1)
            sess = {tuple(t[:len(grao)]): (int(t[-2]), int(t[-1]))
                    for t in rel(grao, ["sessions", "engagedSessions"], ini, DOMINGO)}
            tot = defaultdict(lambda: [0, 0])
            for k, v in rolling.items():
                ses, eng = sess.get(k, (0, 0))
                tot[site(k[0])][0] += v[i]
                if not robotico(ses, eng):
                    tot[site(k[0])][1] += v[i]
            for s, (sm, va) in sorted(tot.items()):
                ex = exato[(s, dom)][i]
                print(f"     {s:14} {nome}  exato={ex:>7}  soma={sm:>7} ({(sm/ex-1)*100:+.1f}%)  válido={va:>6}")

    # --- 6. quem são os usuários do Institucional (bots?) ----------------------
    print("\n6) Institucional — top países por WAU (domingo) e engajamento da semana:")
    w = {t[0]: int(t[1]) for t in rel(["country"], ["active7DayUsers"], DOMINGO, DOMINGO)}
    s7 = {t[0]: (int(t[1]), int(t[2])) for t in
          rel(["country"], ["sessions", "engagedSessions"], SEGUNDA, DOMINGO)}
    for c, u in sorted(w.items(), key=lambda x: -x[1])[:8]:
        ses, eng = s7.get(c, (0, 0))
        print(f"   {c:20} WAU={u:>6}  sessões={ses:>6}  taxa_eng={eng/ses*100 if ses else 0:5.1f}%")
