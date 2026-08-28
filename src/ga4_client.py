"""Cliente da GA4 Data API v1beta.

Autentica via Service Account (sem token manual, sem expiração) e expõe
`extrair_eventos(inicio, fim)`, que faz o runReport no grão do modelo,
seguindo a paginação por offset e devolvendo linhas já achatadas em dicts
com as chaves de config.DIMENSOES + config.METRICAS.
"""

import time

import google.auth
import google.auth.transport.requests
import requests

from config import (
    DIMENSOES,
    GA4_CREDENTIALS_PATH,
    GA4_PROPERTY_ID,
    GA4_SCOPES,
    METRICAS,
)

_BASE_URL = "https://analyticsdata.googleapis.com/v1beta"
_PAGE_SIZE = 100_000          # runReport aceita até 250k; 100k é folgado p/ o volume real
REQUEST_TIMEOUT = 90
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2        # segundos: 2, 4, 6...

_creds = None


def _token():
    """Reaproveita as credenciais e só renova o access token quando expira."""
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


def extrair_eventos(inicio, fim):
    """runReport no grão do modelo para [inicio, fim], com paginação por offset.

    Retorna uma lista de dicts (uma por combinação de dimensões), cada um com
    as chaves de DIMENSOES (incl. 'date') e METRICAS, valores como string —
    exatamente como a API devolve.
    """
    base_payload = {
        "dateRanges": [{"startDate": inicio.isoformat(), "endDate": fim.isoformat()}],
        "dimensions": [{"name": d} for d in DIMENSOES],
        "metrics": [{"name": m} for m in METRICAS],
        "keepEmptyRows": False,
        "limit": _PAGE_SIZE,
    }

    registros = []
    offset = 0
    while True:
        payload = {**base_payload, "offset": offset}
        resposta = _run_report(payload)
        pagina = _linhas_para_dicts(resposta)
        registros.extend(pagina)

        total = int(resposta.get("rowCount", 0))
        offset += _PAGE_SIZE
        if offset >= total or not pagina:
            break
        time.sleep(0.5)

    return registros


if __name__ == "__main__":
    from datetime import date, timedelta

    ontem = date.today() - timedelta(days=1)
    dados = extrair_eventos(ontem, ontem)
    print(f"{len(dados)} linhas para {ontem}")
    for d in dados[:5]:
        print(d)
