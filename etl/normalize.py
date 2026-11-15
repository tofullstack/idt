import re

def _pick(d: dict, *chaves, default=None):
    for k in chaves:
        if d.get(k) not in (None, ""):
            return d[k]
    return default

def _digitos(s): return re.sub(r"\D", "", str(s or ""))

def _num(v):
    if v in (None, ""): return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try: return float(s)
    except ValueError: return 0.0

def _data(v):
    s = str(v or "")[:10]
    if re.match(r"\d{2}/\d{2}/\d{4}", s):
        return f"{s[6:10]}-{s[3:5]}-{s[0:2]}"
    return s or None

def de_compras(c: dict, orgao: str):
    cnpj = _digitos(_pick(c, "niFornecedor", "ni_fornecedor"))
    ug = str(_pick(c, "codigoUnidadeGestora", default=""))
    ident = _pick(c, "id", "idContrato", "numeroControlePncpContrato")
    if not ident:
        partes = [orgao, ug, _pick(c, "codigoUnidadeGestoraOrigemContrato", default=""),
                  _pick(c, "codigoTipo", default=""), _pick(c, "numeroContrato", default=""), cnpj]
        ident = "-".join(str(p) for p in partes if str(p))
    excluir = None
    if c.get("contratoExcluido") is True or _pick(c, "dataHoraExclusao"):
        excluir = "contrato excluído"
    elif str(c.get("receitaDespesa") or "D").upper() == "R":
        excluir = "contrato de receita (não é gasto)"
    return dict(
        id=f"compras:{ident}", fonte="compras", orgao=orgao, ug=ug, cnpj=cnpj,
        ni=str(_pick(c, "niFornecedor", "ni_fornecedor", default="")).strip(),
        inclusao=str(c.get("dataHoraInclusao") or ""),
        nome=_pick(c, "nomeRazaoSocialFornecedor", "nomeFornecedor", default=""),
        objeto=_pick(c, "objeto", default=""),
        valor=_num(_pick(c, "valorGlobal", "valorInicial", "valorParcela")),
        data_inicio=_data(_pick(c, "dataVigenciaInicial", "dataAssinatura")),
        data_fim=_data(_pick(c, "dataVigenciaFinal")), excluir=excluir)

def de_transparencia(c: dict, orgao: str):
    f = c.get("fornecedor") or {}
    return dict(
        id=f"transparencia:{c.get('id')}", fonte="transparencia", orgao=orgao, ug="", ni="", inclusao="",
        cnpj=_digitos(_pick(f, "cnpjFormatado", "cpfCnpj")),
        nome=_pick(f, "nome", "razaoSocial", default=""),
        objeto=_pick(c, "objeto", default=""),
        valor=_num(_pick(c, "valorInicialCompra", "valorFinalCompra")),
        data_inicio=_data(_pick(c, "dataInicioVigencia")),
        data_fim=_data(_pick(c, "dataFimVigencia")), excluir=None)


def auditar_compras(c: dict, orgao: str):
    """normaliza 1 registro e lista o que não foi preenchido (para calibrar os nomes de campo)."""
    n = de_compras(c, orgao)
    problemas = []
    if len(n["cnpj"]) != 14: problemas.append("cnpj do fornecedor (esperado 14 dígitos)")
    if not n["valor"]:       problemas.append("valor (0 ou campo não encontrado)")
    if not n["data_inicio"]: problemas.append("data_inicio")
    if not n["objeto"]:      problemas.append("objeto")
    if not n["nome"]:        problemas.append("nome do fornecedor")
    if n["excluir"]:         problemas.append(f"seria DESCARTADO: {n['excluir']}")
    if n["id"].endswith("-") or n["id"].startswith("compras:None"):
        problemas.append("id estável (usando fallback frágil)")
    candidatos = {k: c[k] for k in c if any(t in k.lower() for t in
                  ("valor", "data", "fornecedor", "objeto", "numero", "id", "cnpj", "niforn"))}
    return n, problemas, candidatos
