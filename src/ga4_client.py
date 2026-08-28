"""Cliente da GA4 Data API v1beta.

Autentica via Service Account (sem token manual, sem expiração) e expõe dois
relatórios (ver testes/ACHADOS.md):
  - extrair_site(inicio, fim)    -> uso do site, sem dimensão personalizada
  - extrair_paineis(inicio, fim) -> eventos de painel, com customEvent:nome_painel

Ambos seguem a paginação por offset e devolvem linhas achatadas em dicts.
"""

import time

import google.auth
import google.auth.transport.requests
import requests

from config import (
    DIMENSOES_PAINEL,
    DIMENSOES_SITE,
    EVENTOS_PAINEL,
    GA4_CREDENTIALS_PATH,
    GA4_PROPERTY_ID,
    GA4_SCOPES,
    METRICAS,
)

_BASE_URL = "https://analyticsdata.googleapis.com/v1beta"
_PAGE_SIZE = 100_000
REQUEST_TIMEOUT = 90
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2        # segundos: 2, 4, 6...

_creds = None


def _token():
    global _creds
    if _creds is None:
        _creds, _ = google.auth.load_credentials_from_file(
            GA4_CREDENTIALS_PATH, scopes=GA4_SCOPES
        )
    if not _creds.valid:
        _creds.refresh(google.auth.transport.requests.Request())
    return _creds.token


def _run_report(payload):
    url = f"{_BASE_URL}/properties/{GA4_PROPERTY_ID}:runReport"
    last_error = None
    for tentativa in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {_token()}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            else:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        except requests.RequestException as exc:
            last_error = str(exc)

        if tentativa < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_BASE * tentativa)

    raise RuntimeError(f"runReport falhou após {MAX_RETRIES} tentativas: {last_error}")


def _linhas_para_dicts(resposta):
    dim_headers = [h["name"] for h in resposta.get("dimensionHeaders", [])]
    met_headers = [h["name"] for h in resposta.get("metricHeaders", [])]
    registros = []
    for row in resposta.get("rows", []):
        registro = {}
        for nome, celula in zip(dim_headers, row.get("dimensionValues", [])):
            registro[nome] = celula.get("value")
        for nome, celula in zip(met_headers, row.get("metricValues", [])):
            registro[nome] = celula.get("value")
        registros.append(registro)
    return registros


def _extrair(dimensoes, inicio, fim, dimension_filter=None):
    base_payload = {
        "dateRanges": [{"startDate": inicio.isoformat(), "endDate": fim.isoformat()}],
        "dimensions": [{"name": d} for d in dimensoes],
        "metrics": [{"name": m} for m in METRICAS],
        "keepEmptyRows": False,
        "limit": _PAGE_SIZE,
    }
    if dimension_filter is not None:
        base_payload["dimensionFilter"] = dimension_filter

    registros = []
    offset = 0
    while True:
        resposta = _run_report({**base_payload, "offset": offset})
        pagina = _linhas_para_dicts(resposta)
        registros.extend(pagina)

        total = int(resposta.get("rowCount", 0))
        offset += _PAGE_SIZE
        if offset >= total or not pagina:
            break
        time.sleep(0.5)

    return registros


def extrair_site(inicio, fim):
    """Report A — uso do site, todas as dimensões menos a personalizada."""
    return _extrair(DIMENSOES_SITE, inicio, fim)


def extrair_paineis(inicio, fim):
    """Report B — só eventos de painel, com customEvent:nome_painel."""
    filtro = {
        "filter": {
            "fieldName": "eventName",
            "inListFilter": {"values": EVENTOS_PAINEL},
        }
    }
    return _extrair(DIMENSOES_PAINEL, inicio, fim, dimension_filter=filtro)


if __name__ == "__main__":
    from datetime import date, timedelta

    ontem = date.today() - timedelta(days=1)
    print(f"site   {ontem}: {len(extrair_site(ontem, ontem))} linhas")
    print(f"painel {ontem}: {len(extrair_paineis(ontem, ontem))} linhas")
