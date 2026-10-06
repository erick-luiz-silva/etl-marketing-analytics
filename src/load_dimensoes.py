"""Aplica sql/seed_dim_painel.sql (painéis do Data Insights, aliases e IDs de relatório). Idempotente."""

from pathlib import Path

from db import get_connection

SEED = Path(__file__).resolve().parent.parent / "sql" / "seed_dim_painel.sql"


def carregar_dim_painel():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SEED.read_text(encoding="utf-8"))
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tipo, count(*) FROM silver.dim_painel WHERE ativo GROUP BY tipo ORDER BY tipo;"
            )
            for tipo, n in cur.fetchall():
                print(f"  silver.dim_painel ({tipo}): {n}")
            cur.execute("SELECT count(*) FROM silver.dim_painel_alias;")
            print(f"  silver.dim_painel_alias: {cur.fetchone()[0]}")
            cur.execute("SELECT fonte, count(*) FROM silver.dim_painel_relatorio GROUP BY 1 ORDER BY 1;")
            for fonte, n in cur.fetchall():
                print(f"  silver.dim_painel_relatorio ({fonte}): {n}")


if __name__ == "__main__":
    carregar_dim_painel()
