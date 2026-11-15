import argparse, io, json, os, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests

UASG_URL = "https://dadosabertos.compras.gov.br/modulo-uasg/1.1_consultarUasg_CSV"
CONTRATOS_URL = "https://dadosabertos.compras.gov.br/modulo-contratos/1_consultarContratos"
DATA = os.path.join(os.path.dirname(__file__), "data")

LIMITE_FEDERAL = 80000
COLS = ["codigo_orgao", "cnpj_orgao", "exemplo_uasg", "ano", "http", "n_registros",
        "total", "nome_orgao", "amostra_orgao", "erro"]

_RODAPE = re.compile(r"totalRegistros:\s*(\d+);\s*totalPaginas:\s*(\d+);\s*paginasRestantes:\s*(\d+)")

def parse_uasg_csv(texto: str):
    """separa a linha-rodapé de paginação dos dados. retorna (dataframe, total_paginas|none)."""
    total_paginas = None
    linhas = []
    for ln in texto.splitlines():
        m = _RODAPE.search(ln)
        if m:
            total_paginas = int(m.group(2)); continue
        if ln.strip():
            linhas.append(ln)
    df = pd.read_csv(io.StringIO("\n".join(linhas)), sep=";", dtype=str)
    return df, total_paginas

def baixar_uasgs(status: bool, pausa=0.5):
    pagina, total, partes = 1, None, []
    cache = os.path.join(DATA, "cache"); os.makedirs(cache, exist_ok=True)
    while total is None or pagina <= total:
        arq = os.path.join(cache, f"uasg_{str(status).lower()}_{pagina}.csv")
        if os.path.exists(arq):
            texto = open(arq, encoding="utf-8").read()
        else:
            r = requests.get(UASG_URL, params=dict(pagina=pagina, statusUasg=str(status).lower()),
                             headers={"accept": "text/csv"}, timeout=60)
            r.raise_for_status()
            texto = r.content.decode("utf-8")
            open(arq, "w", encoding="utf-8").write(texto); time.sleep(pausa)
        df, tp = parse_uasg_csv(texto)
        total = tp or total or pagina
        partes.append(df)
        print(f"statusUasg={status} pág {pagina}/{total} ({len(df)} linhas)", flush=True)
        pagina += 1
    out = pd.concat(partes, ignore_index=True)
    out["status_uasg"] = str(status).lower()
    return out

def agregar_orgaos(df: pd.DataFrame, limite=LIMITE_FEDERAL) -> pd.DataFrame:
    d = df.copy()
    d["codigo_orgao"] = d["codigo_orgao"].str.strip()
    d["co_num"] = pd.to_numeric(d["codigo_orgao"], errors="coerce")
    g = (d.groupby("codigo_orgao", dropna=True)
           .agg(cnpj_orgao=("cnpj_cpf_orgao", "first"), n_uasgs=("codigo_uasg", "count"),
                uf_principal=("sigla_uf", lambda s: s.mode().iat[0] if not s.mode().empty else ""),
                exemplo_uasg=("nome_uasg", "first"), co_num=("co_num", "first"),
                n_ativas=("status_uasg", lambda x: int((x == "true").sum())) if "status_uasg" in d else ("codigo_uasg", "count"))
           .reset_index())
    g["escopo"] = g["co_num"].apply(lambda v: "FEDERAL_PROVAVEL" if pd.notna(v) and v < limite else "NAO_FEDERAL")
    return g.drop(columns="co_num").sort_values(["escopo", "n_uasgs"], ascending=[True, False])

def sondar(codigo: str, ano: int):
    """1 consulta ao endpoint de contratos (com retry). nunca levanta exceção."""
    params = dict(pagina=1, tamanhoPagina=10, codigoOrgao=codigo,
                  dataVigenciaInicialMin=f"{ano}-01-01", dataVigenciaInicialMax=f"{ano}-12-31")
    r, erro = None, ""
    for t in range(4):
        try:
            r = requests.get(CONTRATOS_URL, params=params, timeout=60)
        except requests.RequestException as e:
            erro = str(e)[:120]; time.sleep(2 ** t); continue
        if r.status_code in (429, 500, 502, 503, 504):
            erro = f"HTTP {r.status_code}"; time.sleep(2 ** (t + 1)); continue
        break
    if r is None or r.status_code != 200:
        return dict(http=getattr(r, "status_code", "ERRO"), n_registros=None, total=None,
                    nome_orgao="", amostra_orgao="", erro=erro or (r.text[:120] if r is not None else ""))
    p = r.json()
    regs = p if isinstance(p, list) else (p.get("resultado") or p.get("content") or [])
    amostra = {k: v for k, v in (regs[0].items() if regs else []) if "rgao" in k.lower() or "unidade" in k.lower()}
    return dict(http=200, n_registros=len(regs),
                total=None if isinstance(p, list) else p.get("totalRegistros"),
                nome_orgao=amostra.get("nomeOrgao", ""),
                amostra_orgao=json.dumps(amostra, ensure_ascii=False), erro="")

def _migrar_probe(saida):
    """garante que o csv existente tenha exatamente as colunas cols (compatível com versões antigas)."""
    if not os.path.exists(saida): return
    d = pd.read_csv(saida, dtype=str)
    if list(d.columns) != COLS:
        for c in COLS:
            if c not in d: d[c] = ""
        d[COLS].to_csv(saida, index=False)

def consolidar(probe: pd.DataFrame) -> pd.DataFrame:
    """pivota contratos por órgão x ano e devolve só quem tem contrato em algum ano sondado."""
    d = probe[probe.http.astype(str) == "200"].copy()
    d["n"] = (pd.to_numeric(d.total, errors="coerce")
                .fillna(pd.to_numeric(d.n_registros, errors="coerce")).fillna(0).astype(int))
    piv = d.pivot_table(index="codigo_orgao", columns="ano", values="n", aggfunc="max", fill_value=0)
    piv.columns = [f"c{a}" for a in piv.columns]
    piv["total"] = piv.sum(axis=1)
    nomes = (d[d.nome_orgao.fillna("") != ""].groupby("codigo_orgao").nome_orgao.first())
    out = piv.join(nomes).reset_index()
    return out[out.total > 0].sort_values("total", ascending=False)

def cmd_probe(args):
    saida = os.path.join(DATA, "orgaos_probe.csv"); _migrar_probe(saida)
    if args.orgao:
        lista = pd.DataFrame([dict(codigo_orgao=args.orgao, cnpj_orgao="", exemplo_uasg="(manual)")])
    else:
        arq = os.path.join(DATA, "orgaos.csv")
        if not os.path.exists(arq):
            raise SystemExit("Falta data/orgaos.csv. Rode antes: uasgs e depois orgaos.")
        lista = pd.read_csv(arq, dtype=str)
        lista = lista[lista.escopo == "FEDERAL_PROVAVEL"]
        if args.somente_validados:
            v = os.path.join(DATA, "orgaos_validados.csv")
            if not os.path.exists(v): raise SystemExit("Rode 'resumo' antes de usar --somente-validados.")
            lista = lista[lista.codigo_orgao.isin(pd.read_csv(v, dtype=str).codigo_orgao)]
    feitos = set()
    if os.path.exists(saida):
        p = pd.read_csv(saida, dtype=str)
        ok = p[p.http == "200"]
        feitos = set(zip(ok.codigo_orgao, ok.ano))
    tarefas = [(r.codigo_orgao, r.cnpj_orgao, r.exemplo_uasg, ano)
               for r in lista.itertuples() for ano in args.anos
               if args.orgao or (r.codigo_orgao, str(ano)) not in feitos]
    if args.max: tarefas = tarefas[:args.max]
    print(f"{len(tarefas)} consultas pendentes (workers={args.workers})", flush=True)
    novo = not os.path.exists(saida)

    def _uma(t):
        res = sondar(t[0], t[3]); time.sleep(0.3)
        return t, res

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(_uma, t) for t in tarefas]
        for n, f in enumerate(as_completed(futs), 1):
            t, res = f.result()
            linha = pd.DataFrame([dict(codigo_orgao=t[0], cnpj_orgao=t[1], exemplo_uasg=t[2], ano=t[3], **res)])
            linha[COLS].to_csv(saida, mode="a", header=novo, index=False); novo = False
            if n % 25 == 0 or res["http"] != 200 or res["total"]:
                print(f"[{n}/{len(tarefas)}] {t[0]} {t[3]} http={res['http']} total={res['total']}", flush=True)

def cmd_resumo(_):
    saida = os.path.join(DATA, "orgaos_probe.csv")
    if not os.path.exists(saida): raise SystemExit("Rode 'probe' antes.")
    p = pd.read_csv(saida, dtype=str)
    v = consolidar(p); v.to_csv(os.path.join(DATA, "orgaos_validados.csv"), index=False)
    todos = set(zip(p.codigo_orgao, p.ano)); ok = p[p.http == "200"]
    pend = todos - set(zip(ok.codigo_orgao, ok.ano))
    print(f"pares órgão×ano: {len(todos)} | SEM resposta 200 (pendentes): {len(pend)}"
          + (" -> rode o probe de novo para repetir" if pend else ""))
    print(f"órgãos sondados: {p.codigo_orgao.nunique()} | COM contratos: {len(v)}")
    cols = [c for c in v.columns if c.startswith("c") and c != "codigo_orgao"]
    print("contratos por ano (soma dos órgãos sondados):", v[cols].sum().astype(int).to_dict())
    print(v.head(15)[["codigo_orgao", "nome_orgao", "total"]].to_string(index=False))

def cmd_diag(args):
    """varre anos e variações de parâmetro para um código, para distinguir
    'código inválido' de 'órgão sem contratos neste módulo'."""
    c = args.orgao
    print(f"== codigoOrgao={c}: total de contratos por ano de início de vigência ==")
    achou = None
    for ano in range(2020, 2026):
        res = sondar(c, ano)
        print(ano, "http", res["http"], "registros", res["n_registros"], "total", res["total"], res["erro"])
        if res["n_registros"] and not achou: achou = res
        time.sleep(0.7)
    if achou:
        print("\nCAMPOS DE ÓRGÃO/UNIDADE NO 1º CONTRATO:", achou["amostra_orgao"])
        print("-> código VÁLIDO neste módulo.")
    else:
        print("\nNenhum contrato em 2020-2025. Teste agora com um órgão que SEGURAMENTE contrata "
              "(ex.: --orgao 26246, 36000, 20113). Se esses também zerarem, o espaço de códigos é outro.")

def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("uasgs")
    o = sp.add_parser("orgaos"); o.add_argument("--entrada", default=os.path.join(DATA, "uasg_todas.csv"))
    p = sp.add_parser("probe"); p.add_argument("--anos", type=int, nargs="+", default=[2023, 2024])
    p.add_argument("--max", type=int); p.add_argument("--orgao")
    p.add_argument("--workers", type=int, default=1); p.add_argument("--somente-validados", action="store_true")
    sp.add_parser("resumo")
    d = sp.add_parser("diag"); d.add_argument("--orgao", required=True)
    a = ap.parse_args(); os.makedirs(DATA, exist_ok=True)
    if a.cmd == "uasgs":
        df = pd.concat([baixar_uasgs(True), baixar_uasgs(False)], ignore_index=True)
        df = df.drop_duplicates("codigo_uasg", keep="first")
        df.to_csv(os.path.join(DATA, "uasg_todas.csv"), sep=";", index=False)
        print(len(df), "UASGs salvas")
    elif a.cmd == "orgaos":
        if not os.path.exists(a.entrada):
            raise SystemExit(f"Não achei {a.entrada}. Rode antes: python discover_orgaos.py uasgs "
                             "(ou use --entrada data/uasg_pagina1.csv só para teste).")
        df, _ = parse_uasg_csv(open(a.entrada, encoding="utf-8").read())
        ag = agregar_orgaos(df); ag.to_csv(os.path.join(DATA, "orgaos.csv"), index=False)
        print(ag.escopo.value_counts().to_string())
    elif a.cmd == "diag":
        cmd_diag(a)
    elif a.cmd == "resumo":
        cmd_resumo(a)
    else:
        cmd_probe(a)

if __name__ == "__main__":
    main()
