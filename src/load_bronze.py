"""Grava na bronze o resultado de uma extração, uma linha por dia (append-only)."""

import json
from collections import defaultdict

_TABELAS = {
    "site": "bronze.ga4_site_raw",
    "painel": "bronze.ga4_paineis_raw",
}


def gravar_snapshot_diario(conn, relatorio, registros):
    """Agrupa `registros` (lista de dicts com chave 'date') por dia e grava
    um snapshot por dia na tabela bronze do relatório ('site' | 'painel').

    Retorna {event_date: qtd_linhas}.
    """
    tabela = _TABELAS[relatorio]
    por_dia = defaultdict(list)
    for r in registros:
        por_dia[r["date"]].append(r)

    with conn.cursor() as cur:
        for data_str, linhas in sorted(por_dia.items()):
            event_date = f"{data_str[:4]}-{data_str[4:6]}-{data_str[6:]}"
            cur.execute(
                f"INSERT INTO {tabela} (event_date, payload, linhas) VALUES (%s, %s, %s);",
                (event_date, json.dumps(linhas, ensure_ascii=False), len(linhas)),
            )
    conn.commit()

    return {d: len(v) for d, v in por_dia.items()}
