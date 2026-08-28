from contextlib import contextmanager

import psycopg2

from config import DB_CONFIG


@contextmanager
def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()
