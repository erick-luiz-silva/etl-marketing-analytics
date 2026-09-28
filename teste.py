"""
Diagnóstico de frescor (data freshness) da GA4 Data API.

Objetivo: saber quando os dados de ONTEM — inclusive os eventos da tag de
painel (painel_acessado / painel_clicado) — estão consolidados, para calibrar
o horário da carga diária.

Rodar:  python teste.py
"""

import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from ga4_client import _run_report  # noqa: E402


def _fmt_ts(yyyymmddhhmm):
    d = yyyymmddhhmm
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]} {d[8:10]}:{d[10:12] if len(d) > 10 else '00'}"


def metadados():
    r = _run_report({
        "dateRanges": [{"startDate": "yesterday", "endDate": "yesterday"}],
        "dimensions": [{"name": "date"}],
        "metrics": [{"name": "eventCount"}],
        "limit": 1,
    })
    md = r.get("metadata", {})
    return md.get("timeZone"), md.get("dataLossFromGapsTimestamp")


def ultimo_minuto_com_dados():
    r = _run_report({
        "dateRanges": [{"startDate": "3daysAgo", "endDate": "today"}],
        "dimensions": [{"name": "dateHourMinute"}],
        "metrics": [{"name": "eventCount"}],
        "orderBys": [{"dimension": {"dimensionName": "dateHourMinute"}, "desc": True}],
        "limit": 1,
    })
    rows = r.get("rows", [])
    return rows[0]["dimensionValues"][0]["value"] if rows else None


def totais_por_dia():
    r = _run_report({
        "dateRanges": [{"startDate": "6daysAgo", "endDate": "today"}],
        "dimensions": [{"name": "date"}],
        "metrics": [
            {"name": "eventCount"}, {"name": "sessions"},
            {"name": "activeUsers"}, {"name": "userEngagementDuration"},
        ],
        "orderBys": [{"dimension": {"dimensionName": "date"}}],
    })
    return r.get("rows", [])


def tag_painel_por_hora():
    r = _run_report({
        "dateRanges": [{"startDate": "2daysAgo", "endDate": "today"}],
        "dimensions": [{"name": "dateHour"}, {"name": "eventName"}],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {"filter": {
            "fieldName": "eventName",
            "inListFilter": {"values": ["painel_acessado", "painel_clicado"]},
        }},
        "orderBys": [{"dimension": {"dimensionName": "dateHour"}}],
    })
    return r.get("rows", [])


if __name__ == "__main__":
    tz_nome, gap_ts = metadados()
    tz = ZoneInfo(tz_nome) if tz_nome else ZoneInfo("America/Sao_Paulo")
    agora = datetime.now(tz)
    print(f"Timezone da propriedade : {tz_nome}")
    print(f"Agora (nessa timezone)  : {agora:%Y-%m-%d %H:%M}")
    if gap_ts:
        print(f"dataLossFromGapsTimestamp: {gap_ts}")
    print()

    ultimo = ultimo_minuto_com_dados()
    if ultimo:
        dt_ultimo = datetime(
            int(ultimo[0:4]), int(ultimo[4:6]), int(ultimo[6:8]),
            int(ultimo[8:10]), int(ultimo[10:12]), tzinfo=tz,
        )
        lag = agora - dt_ultimo
        print(f"Último minuto com QUALQUER evento: {_fmt_ts(ultimo)}")
        print(f"Defasagem atual (lag)            : {lag} "
              f"(~{lag.total_seconds() / 3600:.1f} h)")
    print()

    print("Totais por dia (últimos 7 — 'hoje' e às vezes 'ontem' vêm parciais):")
    print(f"  {'data':<10} {'eventos':>9} {'sessões':>9} {'usuários':>9} {'engaj_s':>10}")
    for row in totais_por_dia():
        d = row["dimensionValues"][0]["value"]
        ev, se, us, en = (m["value"] for m in row["metricValues"])
        print(f"  {d[:4]}-{d[4:6]}-{d[6:8]} {ev:>9} {se:>9} {us:>9} {float(en):>10.0f}")
    print()

    print("Eventos da tag de painel por hora (últimos 2 dias + hoje):")
    linhas = tag_painel_por_hora()
    if not linhas:
        print("  (nenhum evento de painel no período)")
    for row in linhas:
        dh = row["dimensionValues"][0]["value"]      # YYYYMMDDHH
        ev = row["dimensionValues"][1]["value"]
        n = row["metricValues"][0]["value"]
        print(f"  {dh[:4]}-{dh[4:6]}-{dh[6:8]} {dh[8:10]}h | {ev:<16} | {n}")
    print()

    # -------- veredito --------
    ontem = (agora - timedelta(days=1)).date()
    fim_de_ontem = datetime.combine(agora.date(), time.min, tzinfo=tz)  # hoje 00:00
    print("-" * 60)
    if ultimo and dt_ultimo >= fim_de_ontem:
        print(f"[OK] ONTEM ({ontem}) JA ESTA COMPLETO — a API ja processou "
              f"ate {_fmt_ts(ultimo)}.")
    elif ultimo:
        falta = fim_de_ontem - dt_ultimo
        print(f"[--] ONTEM ({ontem}) AINDA NAO ESTA COMPLETO.")
        print(f"  A API processou até {_fmt_ts(ultimo)} — faltam ~{falta} "
              f"do dia de ontem.")
        print(f"  Nesse ritmo (~{lag.total_seconds() / 3600:.0f}h de defasagem), "
              f"ontem fecha por volta de "
              f"{(dt_ultimo + timedelta(days=1)):%d/%m %Hh}.")
    print("  Regra prática do GA4: dados ficam finais em até 48h; o alvo seguro")
    print("  da carga é D-2. A janela D-3 do pipeline recobre e corrige sozinha.")
