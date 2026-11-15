import time
from datetime import date, timedelta
import requests

URL = "https://dadosabertos.compras.gov.br/modulo-contratos/1_consultarContratos"
TAMANHO = 500

def split_janelas(ini: date, fim: date, dias: int = 365):
    """divide [ini, fim] em janelas de no máximo `dias` dias (inclusivas)."""
    atual = ini
    while atual <= fim:
        topo = min(atual + timedelta(days=dias - 1), fim)
        yield atual, topo
        atual = topo + timedelta(days=1)

def _registros(payload):
    if isinstance(payload, list):
        return payload
    return payload.get("resultado") or payload.get("content") or []

def contratos(codigo_orgao: str, ini: date, fim: date, tamanho: int = TAMANHO):
    for j_ini, j_fim in split_janelas(ini, fim):
        pagina = 1
        while True:
            r = requests.get(URL, params=dict(
                pagina=pagina, tamanhoPagina=tamanho, codigoOrgao=codigo_orgao,
                dataVigenciaInicialMin=j_ini.isoformat(),
                dataVigenciaInicialMax=j_fim.isoformat()), timeout=60)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(10); continue
            r.raise_for_status()
            lote = _registros(r.json())
            if not lote:
                break
            yield from lote
            if len(lote) < tamanho:
                break
            pagina += 1
            time.sleep(0.5)
