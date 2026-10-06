"""Executa sql/transform_bronze_to_silver.sql e imprime contagens.

Por padrão só reprocessa os dias com snapshot novo na bronze. `--completo`
esvazia a silver antes, forçando o reprocessamento do histórico inteiro (usar
quando mudar uma regra da transformação).
"""

import argparse
from pathlib import Path

from db import get_connection

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

CONTAGENS = [
    ("silver.ga4_eventos (total)", "SELECT count(*) FROM silver.ga4_eventos;"),
    ("silver.ga4_eventos (válido)", "SELECT count(*) FROM silver.ga4_eventos WHERE trafego_valido;"),
    ("silver.ga4_eventos (dias)", "SELECT count(DISTINCT event_date) FROM silver.ga4_eventos;"),
    ("silver.ga4_paineis (total)", "SELECT count(*) FROM silver.ga4_paineis;"),
    ("silver.ga4_paineis (dias)", "SELECT count(DISTINCT event_date) FROM silver.ga4_paineis;"),
    ("silver.ga4_usuarios (total)", "SELECT count(*) FROM silver.ga4_usuarios;"),
    ("silver.ga4_usuarios (dias)", "SELECT count(DISTINCT event_date) FROM silver.ga4_usuarios;"),
    ("silver.ga4_paginas (total)", "SELECT count(*) FROM silver.ga4_paginas;"),
    ("silver.ga4_paginas (dias)", "SELECT count(DISTINCT event_date) FROM silver.ga4_paginas;"),
]

TABELAS_SILVER = ["silver.ga4_eventos", "silver.ga4_paineis", "silver.ga4_usuarios",
                  "silver.ga4_paginas"]


def executar_transformacao_silver(completo=False):
    sql = (SQL_DIR / "transform_bronze_to_silver.sql").read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            if completo:
                for tabela in TABELAS_SILVER:
                    cur.execute(f"TRUNCATE {tabela};")
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            for nome, query in CONTAGENS:
                cur.execute(query)
                print(f"  {nome}: {cur.fetchone()[0]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transformação bronze -> silver")
    parser.add_argument("--completo", action="store_true",
                        help="reprocessa todo o histórico (esvazia a silver antes)")
    executar_transformacao_silver(parser.parse_args().completo)
