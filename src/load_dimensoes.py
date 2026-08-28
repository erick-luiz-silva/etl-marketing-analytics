"""Popula silver.dim_painel a partir de src/paineis.py (upsert por termo)."""

from db import get_connection
from paineis import PAINEIS


def carregar_dim_painel():
    with get_connection() as conn:
        with conn.cursor() as cur:
            for rotulo, termo in PAINEIS:
                cur.execute(
                    """
                    INSERT INTO silver.dim_painel (termo, rotulo, ativo)
                    VALUES (%s, %s, true)
                    ON CONFLICT (termo) DO UPDATE SET
                        rotulo = EXCLUDED.rotulo,
                        ativo = true;
                    """,
                    (termo, rotulo),
                )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM silver.dim_painel WHERE ativo;")
            print(f"silver.dim_painel: {cur.fetchone()[0]} termos ativos")


if __name__ == "__main__":
    carregar_dim_painel()
