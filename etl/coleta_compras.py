import json, time
from datetime import date, timedelta
import requests

VERSAO = "janelas-adaptativas-v2"
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

def _get(params):
    ultimo = None
    for t in range(5):
        try:
            r = requests.get(URL, params=params, timeout=60)
        except requests.RequestException as e:
            ultimo = e; time.sleep(2 ** t); continue
        if r.status_code in (429, 500, 502, 503, 504):
            ultimo = f"HTTP {r.status_code}"; time.sleep(2 ** t); continue
        r.raise_for_status()
        time.sleep(0.2)
        return r.json()
    raise requests.RequestException(f"falha após 5 tentativas: {ultimo}")

def _params(orgao, a, b, pagina, tamanho):
    return dict(pagina=pagina, tamanhoPagina=tamanho, codigoOrgao=orgao,
                dataVigenciaInicialMin=a.isoformat(), dataVigenciaInicialMax=b.isoformat())

def _dentro(row, a, b):
    """a api devolve também o dia anterior ao início da janela; descartamos o que está fora de [a, b]."""
    d = str(row.get("dataVigenciaInicial") or "")[:10]
    return (not d) or (a.isoformat() <= d <= b.isoformat())

def _paginar(orgao, a, b, tamanho):
    pagina = 1
    while True:
        lote = _registros(_get(_params(orgao, a, b, pagina, tamanho)))
        if not lote:
            return
        yield from lote
        if len(lote) < tamanho:
            return
        pagina += 1

def _janela(orgao, a, b, tamanho):
    p = _get(_params(orgao, a, b, 1, tamanho))
    regs = _registros(p)
    total = p.get("totalRegistros") if isinstance(p, dict) else None
    if total is None:
        yield from (r for r in _paginar(orgao, a, b, tamanho) if _dentro(r, a, b)); return
    if int(total) <= len(regs):
        yield from (r for r in regs if _dentro(r, a, b)); return
    if a < b:
        meio = a + (b - a) // 2
        yield from _janela(orgao, a, meio, tamanho)
        yield from _janela(orgao, meio + timedelta(days=1), b, tamanho)
        return
    vistos = set()
    for tam in [tamanho] + [t for t in (250, 100) if t < tamanho]:
        for row in _paginar(orgao, a, b, tam):
            if not _dentro(row, a, b): continue
            k = json.dumps(row, sort_keys=True, default=str)
            if k not in vistos:
                vistos.add(k); yield row

def contratos(codigo_orgao: str, ini: date, fim: date, tamanho: int = TAMANHO):
    for a, b in split_janelas(ini, fim):
        yield from _janela(codigo_orgao, a, b, tamanho)
