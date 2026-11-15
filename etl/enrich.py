import re
import config as C

def _any(patterns, texto): return any(re.search(p, texto) for p in patterns)

def marca_hyperscaler(objeto: str) -> bool:
    return _any(C.MARCAS, (objeto or "").lower())

def intermediacao_nuvem(objeto: str) -> bool:
    return _any(C.KW_BROKER, (objeto or "").lower())

def categoria(objeto: str) -> str:
    t = (objeto or "").lower()
    if _any(C.KW_PROJETO_FUNDACAO, t):                           return "OUTRO"
    if _any(C.KW_GUARDA_CHUVA, t):                               return "TIC"
    if _any(C.KW_SUITE_NUVEM, t) and re.search(r"(office|microsoft) ?365", t) and not _any(C.KW_EXCLUIR_NUVEM, t): return "NUVEM"
    if _any(C.KW_IA, t) and not _any(C.KW_EXCLUIR_IA, t):       return "IA"
    if _any(C.KW_NUVEM, t) and not _any(C.KW_EXCLUIR_NUVEM, t): return "NUVEM"
    if _any(C.KW_TELEFONIA, t):                                  return "TIC"
    if _any(C.MARCAS, t):   return "TIC"
    if _any(C.KW_LICENCA_SW, t) and not _any(C.KW_HARDWARE_FORTE, t): return "TIC"
    if _any(C.KW_INFRA, t): return "INFRA"
    if _any(C.KW_TIC, t):   return "TIC"
    return "OUTRO"

def peso_w(objeto: str, origem: str, hyperscaler: bool, indeterminado: str = "zero") -> float:
    """indeterminado='zero': fornecedor não classificado não conta (conservador).
       indeterminado='estrangeiro': conta como estrangeiro (análise de sensibilidade)."""
    hyper = bool(hyperscaler) or marca_hyperscaler(objeto)
    broker = intermediacao_nuvem(objeto)
    if not hyper and not broker:
        if origem == "NACIONAL": return C.W_NACIONAL
        if origem == "INDETERMINADO" and indeterminado == "zero": return C.W_NACIONAL
    t = (objeto or "").lower()
    if _any(C.KW_ABERTO, t):
        return C.W_ABERTO
    if hyper or categoria(objeto) == "IA":
        return C.W_PROPRIETARIO
    if broker:
        return C.W_BROKER
    return C.W_PADRAO
