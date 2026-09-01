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

# São DOIS relatórios (ver testes/ACHADOS.md):
#
# Report A — uso do site. NÃO inclui a dimensão personalizada, então o GA4
# serve das tabelas agregadas e o histórico alcança fev/2023.
DIMENSOES_SITE = [
    "date",
    "hostName",
    "country",
    "region",
    "city",
    "deviceCategory",
    "browser",
    "operatingSystem",
    "eventName",
]
#
# Report B — engajamento por painel. Inclui customEvent:nome_painel, o que faz
# o GA4 cortar tudo antes da criação da dimensão (~jun/2026) e restringir aos
# eventos de painel. Volume ínfimo hoje (~120 eventos).
DIMENSOES_PAINEL = [
    "date",
    "hostName",
    "country",
    "region",
    "city",
    "deviceCategory",
    "eventName",
    "customEvent:nome_painel",
]
EVENTOS_PAINEL = ["painel_acessado", "painel_clicado"]

METRICAS = [
    "eventCount",
    "sessions",
    "engagedSessions",
    "activeUsers",
    "userEngagementDuration",
]

# Datas de corte:
#   - Report A (uso de site): dados desde fev/2023
#   - Report B (painéis): a dimensão nome_painel passou a retornar dados em
#     jun/2026; eventos painel_acessado reais só a partir de 27/08/2026
DATA_INICIO_HISTORICO = date(2023, 2, 1)
DATA_INICIO_PAINEIS = date(2026, 6, 1)

# A GA4 processa dados com 24–48h de atraso; a janela incremental recua 3 dias.
JANELA_SEGURANCA_DIAS = 3
