import json, os, re, time
import requests
from config import HYPERSCALERS

BRASILAPI = "https://brasilapi.com.br/api/cnpj/v1/{}"
MAX_DEPTH = 5
INTERVALO = 0.35
_CACHE: dict = {}
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cnpj")
_ultimo = [0.0]
CNPJWS = "https://publica.cnpj.ws/cnpj/{}"
USAR_CNPJWS = True
INTERVALO_CNPJWS = 21.0
_ultimo_ws = [0.0]

class ConsultaFalhou(Exception):
    pass

def _ler_disco(cnpj: str):
    try:
        with open(os.path.join(CACHE_DIR, f"{cnpj}.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

def _gravar_disco(cnpj: str, dados: dict):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(os.path.join(CACHE_DIR, f"{cnpj}.json"), "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False)
    except OSError:
        pass

def _limpa(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj or "")

def is_hyperscaler(nome: str) -> bool:
    n = (nome or "").lower()
    return any(re.search(p, n) for p in HYPERSCALERS)

def _consulta(cnpj: str):
    """dict (200) | none (404 definitivo). levanta consultafalhou em falha temporária.
    429/rede: até 5 tentativas com espera crescente. 5xx: só 2 tentativas (a brasilapi devolve 500 de forma
    persistente para alguns cnpjs; insistir só deixava o reclassificar ~30 s mais lento por cnpj)."""
    if cnpj in _CACHE:
        return _CACHE[cnpj]
    em_disco = _ler_disco(cnpj)
    if em_disco is not None:
        _CACHE[cnpj] = em_disco; return em_disco
    ultimo = ""
    for t in range(5):
        espera = INTERVALO - (time.time() - _ultimo[0])
        if espera > 0: time.sleep(espera)
        _ultimo[0] = time.time()
        try:
            r = requests.get(BRASILAPI.format(cnpj), timeout=20, headers={"User-Agent": "idt-tcc/0.1"})
        except requests.RequestException as e:
            ultimo = type(e).__name__; time.sleep(2 ** t); continue
        if r.status_code == 200:
            _CACHE[cnpj] = r.json(); _gravar_disco(cnpj, _CACHE[cnpj]); return _CACHE[cnpj]
        if r.status_code == 404:
            _CACHE[cnpj] = None; return None
        ultimo = f"HTTP {r.status_code}"
        if r.status_code >= 500 and t >= 1:
            break
        time.sleep(1 if r.status_code >= 500 else 2 ** t)
    if USAR_CNPJWS:
        try:
            d = _consulta_cnpjws(cnpj)
        except ConsultaFalhou as e:
            raise ConsultaFalhou(f"{ultimo}; {e}")
        _CACHE[cnpj] = d
        if d is not None: _gravar_disco(cnpj, d)
        return d
    raise ConsultaFalhou(ultimo)

def _de_cnpjws(j: dict) -> dict:
    """converte a resposta da publica.cnpj.ws para o formato da brasilapi usado por classificar()."""
    qsa = []
    for x in j.get("socios") or []:
        tipo = str(x.get("tipo") or "").lower()
        pais = x.get("pais") or {}
        iso = str(pais.get("iso2") or "").upper()
        qual = (x.get("qualificacao_socio") or {}).get("descricao") or ""
        qsa.append(dict(
            identificador_de_socio=3 if "estrangeir" in tipo else (1 if "jur" in tipo else 2),
            nome_socio=x.get("nome") or "",
            cnpj_cpf_do_socio=x.get("cpf_cnpj_socio") or "",
            pais=(pais.get("nome") or "") if iso not in ("BR", "") else "",
            qualificacao_socio=qual))
    nat = j.get("natureza_juridica") or {}
    return dict(razao_social=j.get("razao_social") or "", natureza_juridica=nat.get("descricao") or "",
                qsa=qsa, _fonte="publica.cnpj.ws")

def _consulta_cnpjws(cnpj: str):
    """dict normalizado | none (404). levanta consultafalhou. espaça as chamadas (3/min) e espera quando recebe 429."""
    ultimo = ""
    for t in range(3):
        espera = INTERVALO_CNPJWS - (time.time() - _ultimo_ws[0])
        if espera > 0: time.sleep(espera)
        _ultimo_ws[0] = time.time()
        try:
            r = requests.get(CNPJWS.format(cnpj), timeout=20, headers={"User-Agent": "idt-tcc/0.1"})
        except requests.RequestException as e:
            ultimo = type(e).__name__; continue
        if r.status_code == 200:
            return _de_cnpjws(r.json())
        if r.status_code == 404:
            return None
        ultimo = f"HTTP {r.status_code}"
        if r.status_code == 429:
            time.sleep(30)
        elif r.status_code >= 500:
            break
    raise ConsultaFalhou("cnpj.ws " + ultimo)

def dv_cnpj(base12: str) -> str:
    """dígitos verificadores de um cnpj a partir dos 12 primeiros dígitos (raiz + filial)."""
    def dv(d, pesos):
        r = sum(int(x) * p for x, p in zip(d, pesos)) % 11
        return "0" if r < 2 else str(11 - r)
    d1 = dv(base12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = dv(base12 + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return d1 + d2

def matriz_de(cnpj: str) -> str:
    """cnpj da matriz (filial 0001) da mesma raiz. filiais e matriz são a mesma pessoa jurídica: o quadro societário é o mesmo."""
    b = cnpj[:8] + "0001"
    return b + dv_cnpj(b)

def _consulta_entidade(cnpj: str):
    """consulta a matriz primeiro (resolve filiais que dão http 500 e reaproveita o cache entre filiais da mesma raiz);
    se a matriz não responder ou não existir, tenta o cnpj original."""
    if cnpj[8:12] != "0001":
        try:
            d = _consulta(matriz_de(cnpj))
            if d: return d
        except ConsultaFalhou:
            pass
    return _consulta(cnpj)

def _pais_estrangeiro(pais) -> bool:
    p = (pais or "").strip().lower()
    return bool(p) and p not in ("brasil", "brazil", "br")

def _socio_exterior(s: dict) -> bool:
    """confirmado com a brasilapi (dell, lenovo, siemens): sócio pj estrangeiro vem com identificador_de_socio=1 (não 3),
    cnpj_cpf_do_socio de 8 dígitos (inútil para recursão), pais preenchido e qualificação 'sócio pessoa jurídica
    domiciliado no exterior'."""
    return (s.get("identificador_de_socio") == 3 or _pais_estrangeiro(s.get("pais"))
            or "exterior" in str(s.get("qualificacao_socio") or "").lower())

def _natureza_exterior(dados: dict) -> bool:
    """empresa domiciliada no exterior com cnpj no brasil: não tem qsa próprio, então a recursão pararia em 'nacional'.
    hipótese a confirmar com buscar_fornecedor.py (campo natureza_juridica da brasilapi)."""
    return bool(re.search(r"exterior|estrangeir", str(dados.get("natureza_juridica") or ""), re.I))

def _indet(motivo):
    return dict(origem="INDETERMINADO", hyperscaler=False, ubo=None, motivo=motivo)

def classificar(cnpj: str, razao_social: str = "", _depth: int = 0, _visitados=None) -> dict:
    cnpj = _limpa(cnpj)
    _visitados = _visitados if _visitados is not None else set()

    if is_hyperscaler(razao_social):
        return dict(origem="ESTRANGEIRO", hyperscaler=True, ubo=razao_social, motivo="Lista de hyperscalers")
    if len(cnpj) != 14 or cnpj in _visitados or _depth > MAX_DEPTH:
        return _indet("CNPJ inválido, ciclo ou profundidade máxima")
    _visitados.add(cnpj)

    try:
        dados = _consulta_entidade(cnpj)
    except ConsultaFalhou as e:
        return _indet(f"Falha na consulta ({e})")
    if not dados:
        return _indet("CNPJ não encontrado na BrasilAPI (404)")
    if is_hyperscaler(dados.get("razao_social", "")):
        return dict(origem="ESTRANGEIRO", hyperscaler=True, ubo=dados["razao_social"],
                    motivo="Lista de hyperscalers (razão social oficial)")

    if _natureza_exterior(dados):
        return dict(origem="ESTRANGEIRO", hyperscaler=False, ubo=dados.get("razao_social"),
                    motivo=f"Natureza jurídica no exterior (nível {_depth})")

    incompleta = None
    for s in dados.get("qsa") or []:
        if _socio_exterior(s):
            return dict(origem="ESTRANGEIRO", hyperscaler=False,
                        ubo=s.get("nome_socio"), motivo=f"Sócio estrangeiro (nível {_depth})")
        if s.get("identificador_de_socio") == 1:
            doc = _limpa(s.get("cnpj_cpf_do_socio", ""))
            if len(doc) == 14:
                r = classificar(doc, s.get("nome_socio", ""), _depth + 1, _visitados)
                if r["origem"] == "ESTRANGEIRO":
                    r["motivo"] = f"Cadeia societária (nível {_depth + 1}): " + r["motivo"]
                    return r
                if "Falha" in r["motivo"]:
                    incompleta = r["motivo"]
    if incompleta:
        return _indet(f"Cadeia incompleta: {incompleta}")
    return dict(origem="NACIONAL", hyperscaler=False, ubo=None, motivo="QSA sem controlador estrangeiro identificado")
