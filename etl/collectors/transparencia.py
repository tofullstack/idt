import time
import requests
from config import TRANSPARENCIA_API_KEY

BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"

def contratos(codigo_orgao: str, data_ini: str, data_fim: str):
    """gera dicts brutos. datas em dd/mm/aaaa."""
    pagina = 1
    while True:
        r = requests.get(
            f"{BASE}/contratos",
            headers={"chave-api-dados": TRANSPARENCIA_API_KEY},
            params=dict(codigoOrgao=codigo_orgao, dataInicial=data_ini,
                        dataFinal=data_fim, pagina=pagina),
            timeout=30,
        )
        if r.status_code == 429:
            time.sleep(60); continue
        r.raise_for_status()
        lote = r.json()
        if not lote:
            return
        yield from lote
        pagina += 1
        time.sleep(0.7)
