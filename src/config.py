import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID")
GA4_CREDENTIALS_PATH = str(_ROOT / os.getenv("GA4_CREDENTIALS_PATH", "config/credentials.json"))
GA4_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

# Grão da extração — validado no teste 5 (588 linhas/dia). São 9 dimensões,
# o máximo que o runReport aceita numa chamada. Origem de tráfego
# (sessionDefaultChannelGroup) ficaria como um 2º relatório se necessário.
DIMENSOES = [
    "date",
    "hostName",
    "country",
    "city",
    "deviceCategory",
    "browser",
    "operatingSystem",
    "eventName",
    "customEvent:nome_painel",
]
METRICAS = [
    "eventCount",
    "sessions",
    "engagedSessions",
    "activeUsers",
    "userEngagementDuration",
]

# Datas de corte (ver testes/ACHADOS.md):
#   - métricas de site (page_view, session_start...) existem desde fev/2023
#   - a tag painel_acessado e a dimensão nome_painel entraram em 27/08/2026
DATA_INICIO_HISTORICO = date(2023, 2, 1)
DATA_INICIO_PAINEIS = date(2026, 8, 27)

# A GA4 processa dados com 24–48h de atraso; a janela incremental recua 3 dias.
JANELA_SEGURANCA_DIAS = 3
