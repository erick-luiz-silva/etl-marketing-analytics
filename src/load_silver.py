"""Executa sql/transform_bronze_to_silver.sql e imprime contagens."""

from pathlib import Path

from db import get_connection

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

CONTAGENS = [
    ("silver.ga4_eventos (total)", "SELECT count(*) FROM silver.ga4_eventos;"),
    ("silver.ga4_eventos (válido)", "SELECT count(*) FROM silver.ga4_eventos WHERE trafego_valido;"),
    ("dias distintos", "SELECT count(DISTINCT event_date) FROM silver.ga4_eventos;"),
]


def executar_transformacao_silver():
    sql = (SQL_DIR / "transform_bronze_to_silver.sql").read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            for nome, query in CONTAGENS:
                cur.execute(query)
                print(f"  {nome}: {cur.fetchone()[0]}")


if __name__ == "__main__":
    executar_transformacao_silver()
