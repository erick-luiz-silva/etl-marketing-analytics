"""Ponto de entrada diário (Task Scheduler).

bronze incremental -> silver -> confere gold. Loga em logs/pipeline.log.
"""

import logging
import sys
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("pipeline")

from db import get_connection  # noqa: E402
from extract_incremental import executar_carga_incremental  # noqa: E402

GOLD_CONTAGENS = [
    ("gold.vw_paineis_ranking", "SELECT count(*) FROM gold.vw_paineis_ranking;"),
    ("gold.vw_site_overview", "SELECT count(*) FROM gold.vw_site_overview;"),
    ("gold.vw_paineis_sem_mapeamento", "SELECT count(*) FROM gold.vw_paineis_sem_mapeamento;"),
]


def resumo_gold():
    with get_connection() as conn:
        with conn.cursor() as cur:
            for nome, query in GOLD_CONTAGENS:
                cur.execute(query)
                logger.info("%s: %s linhas", nome, cur.fetchone()[0])


def main():
    inicio = time.monotonic()
    logger.info("=== Pipeline diário iniciado ===")
    try:
        executar_carga_incremental()
        resumo_gold()
    except Exception:
        logger.exception("Pipeline falhou")
        sys.exit(1)
    logger.info("=== Concluído em %.1fs ===", time.monotonic() - inicio)


if __name__ == "__main__":
    main()
