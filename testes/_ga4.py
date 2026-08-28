"""Helper compartilhado dos scripts de teste.

Autentica via Service Account (config/credentials.json) e expõe funções
finas sobre a GA4 Data API v1beta usando só `requests`.
"""

import json
import os
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROPERTY_ID = os.environ["GA4_PROPERTY_ID"]
_CREDS_PATH = os.getenv("GA4_CREDENTIALS_PATH", "config/credentials.json")
_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
_BASE = "https://analyticsdata.googleapis.com/v1beta"

_ROOT = Path(__file__).resolve().parent.parent


def get_token():
    creds, _ = google.auth.load_credentials_from_file(
        str(_ROOT / _CREDS_PATH), scopes=_SCOPES
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _post(endpoint, payload, token):
    resp = requests.post(
        f"{_BASE}/properties/{PROPERTY_ID}:{endpoint}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=60,
    )
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}\n{resp.text}")
        resp.raise_for_status()
    return resp.json()


def run_report(payload, token=None):
    return _post("runReport", payload, token or get_token())


def get_metadata(token=None):
    token = token or get_token()
    resp = requests.get(
        f"{_BASE}/properties/{PROPERTY_ID}/metadata",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def rows_to_tuples(report):
    """Achata a resposta do runReport em lista de tuplas (dims..., metrics...)."""
    out = []
    for row in report.get("rows", []):
        dims = tuple(d["value"] for d in row.get("dimensionValues", []))
        mets = tuple(m["value"] for m in row.get("metricValues", []))
        out.append(dims + mets)
    return out
