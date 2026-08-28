"""Grava na bronze o resultado de uma extração, uma linha por dia (append-only)."""

import json
from collections import defaultdict

from ga4_client import extrair_eventos

_INSERT = """
    INSERT INTO bronze.ga4_eventos_raw (event_date, payload, linhas)
    VALUES (%s, %s, %s);
"""


def carregar_periodo_bronze(conn, inicio, fim):
    """Extrai [inicio, fim] do GA4 e grava um snapshot por dia na bronze.

    Retorna {event_date: qtd_linhas}.
    """
    registros = extrair_eventos(inicio, fim)

    por_dia = defaultdict(list)
    for r in registros:
        por_dia[r["date"]].append(r)

    with conn.cursor() as cur:
        for data_str, linhas in sorted(por_dia.items()):
            event_date = f"{data_str[:4]}-{data_str[4:6]}-{data_str[6:]}"
            cur.execute(
                _INSERT,
                (event_date, json.dumps(linhas, ensure_ascii=False), len(linhas)),
            )
    conn.commit()

    return {d: len(v) for d, v in por_dia.items()}
