import argparse, json, os
import numpy as np
import pandas as pd
import db, pipeline

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ARQ, GAB, META = (os.path.join(DATA, f) for f in ("rotulagem.csv", "rotulagem_gabarito.csv", "rotulagem_meta.json"))
CATS = ["NUVEM", "IA", "INFRA", "TIC"]
VALIDOS = CATS + ["OUTRO"]
CSV = dict(sep=";", encoding="utf-8-sig")

GUIA = """GUIA DE ROTULAGEM - preencha a coluna 'rotulo' com UMA destas palavras, olhando só o objeto do contrato:
NUVEM : serviço de computação em nuvem (IaaS/PaaS/SaaS) ou assinatura de plataforma/software hospedado pelo fornecedor
        (ex.: AWS, Azure, Microsoft 365, Google Workspace, Adobe Creative Cloud).
IA    : o objeto PRINCIPAL é inteligência artificial / machine learning (plataforma, modelo, assistente, serviço de IA).
        NÃO é IA: curso/treinamento sobre IA, apoio a projeto de pesquisa, serviço que apenas cita IA de passagem.
INFRA : infraestrutura de TI: servidores, storage, switches, redes, links, datacenter próprio (on-premises).
TIC   : demais compras/serviços de TI: software e licenças locais, computadores, impressão, suporte, sistemas, segurança da informação.
OUTRO : não é TI.
Se o objeto mistura coisas, escolha pelo item de maior peso. Em dúvida real, escreva OUTRO e anote o caso à parte."""

def wilson(k, n, z=1.96):
    if n == 0: return float("nan"), float("nan")
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return float(c - h), float(c + h)

def exportar(n=30, n_desc=120, forcar=False, seed=42, n_nuvem_ia=None):
    if os.path.exists(ARQ) and not forcar:
        raise SystemExit(f"{ARQ} já existe (pode conter rótulos seus). Use --forcar só se quiser APAGAR e refazer.")
    os.makedirs(DATA, exist_ok=True)
    conn = db.connect(); db.init_schema(conn)
    partes, pops = [], {}
    for cat in CATS:
        df = pd.read_sql("SELECT c.id, c.valor, c.objeto, c.categoria AS categoria_auto FROM contrato c WHERE c.categoria = '%s'" % cat, conn)
        pops[cat] = len(df)
        if len(df):
            nn = n_nuvem_ia if (n_nuvem_ia and cat in ("NUVEM", "IA")) else n
            a = df.sample(n=min(nn, len(df)), random_state=seed); a["estrato"] = cat; partes.append(a)
    d = pd.read_sql("SELECT id, valor, objeto FROM amostra_descartados", conn)
    pops["DESCARTADO"] = len(d) * pipeline.FRACAO
    if len(d):
        a = d.sample(n=min(n_desc, len(d)), random_state=seed); a["categoria_auto"] = "OUTRO"; a["estrato"] = "DESCARTADO"; partes.append(a)
    conn.close()
    if not partes: raise SystemExit("Banco vazio: rode o pipeline antes.")
    todo = pd.concat(partes, ignore_index=True).sample(frac=1, random_state=seed)
    todo[["id", "valor", "objeto"]].assign(rotulo="").to_csv(ARQ, index=False, **CSV)
    todo[["id", "estrato", "categoria_auto"]].to_csv(GAB, index=False, **CSV)
    json.dump(dict(populacao=pops, seed=seed, fracao_descartados=pipeline.FRACAO), open(META, "w"))
    open(os.path.join(DATA, "rotulagem_guia.txt"), "w", encoding="utf-8").write(GUIA)
    print(GUIA); print(f"\n{len(todo)} contratos para rotular em: {ARQ}\nNão abra {GAB} antes de terminar (rotulagem cega).")

def revisar(frac=0.15, seed=7):
    """rotulagem assistida: usa rótulos propostos por um segundo avaliador (data/rotulos_llm.csv: id;rotulo_llm),
    pré-preenche 'rotulo' e marca para revisão humana (coluna 'revisar' = sim) (a) toda linha em que o proposto difere da
    categoria automática e (b) uma amostra aleatória (frac) das linhas em que concordam. quem revisa não vê a categoria
    automática. o rótulo final é o humano nas linhas sim; nas demais vale o proposto (a amostra de concordâncias estima o erro dele)."""
    prop = os.path.join(DATA, "rotulos_llm.csv")
    if not os.path.exists(prop): raise SystemExit(f"Falta {prop} (colunas: id;rotulo_llm).")
    r, c, g = _ler(ARQ), _ler(prop), _ler(GAB)
    if r["rotulo"].fillna("").str.strip().ne("").any():
        raise SystemExit("rotulagem.csv já tem rótulos preenchidos por você; não vou sobrescrever. Mova o arquivo e tente de novo.")
    d = r.drop(columns=["rotulo"]).merge(c[["id", "rotulo_llm"]], on="id", how="left").merge(g[["id", "categoria_auto"]], on="id")
    d["rotulo"] = d["rotulo_llm"].fillna("").str.strip().str.upper()
    d.loc[~d["rotulo"].isin(VALIDOS), "rotulo"] = ""
    diverge = d["rotulo"].ne(d["categoria_auto"])
    conc = d[~diverge]
    amostra = conc.sample(frac=frac, random_state=seed) if len(conc) else conc
    d["revisar"] = np.where(diverge | d["id"].isin(amostra["id"]), "SIM", "NAO")
    d[["id", "valor", "objeto", "rotulo", "revisar"]].to_csv(ARQ, index=False, **CSV)
    json.dump(dict(n=len(d), divergentes=int(diverge.sum()), concordantes=int(len(conc)),
                   amostra_concordantes=int(len(amostra)), frac=frac, seed=seed),
              open(os.path.join(DATA, "rotulagem_revisao_meta.json"), "w"))
    print(f"{len(d)} linhas pré-preenchidas; {int((d['revisar'] == 'SIM').sum())} para você revisar "
          f"({int(diverge.sum())} divergentes + {len(amostra)} concordâncias sorteadas). No Sheets, filtre revisar = SIM.")

ARQ_CEGO = os.path.join(DATA, "rotulagem_cego.csv")

def cego(n=60, seed=11):
    """rotulagem cega da autora: sorteia n contratos entre os que ela não revisou antes (revisar = nao), sem mostrar
    valor, categoria automática nem sugestão do llm. serve de referência independente para acurácia e kappa."""
    r = _ler(ARQ)
    if "revisar" not in r.columns: raise SystemExit("Rode 'revisar' antes (falta a coluna revisar).")
    pool = r[r["revisar"].astype(str).str.upper().eq("NAO")]
    prop = os.path.join(DATA, "rotulos_llm.csv")
    if os.path.exists(prop):
        pool = pool.merge(_ler(prop)[["id", "rotulo_llm"]], on="id", how="left")
        cota = max(1, n // 5); partes = [g.sample(n=min(cota, len(g)), random_state=seed) for _, g in pool.groupby("rotulo_llm")]
        a = pd.concat(partes); falta = n - len(a)
        if falta > 0: a = pd.concat([a, pool[~pool["id"].isin(a["id"])].sample(n=min(falta, len(pool) - len(a)), random_state=seed)])
        a = a.sample(frac=1, random_state=seed)
    else:
        a = pool.sample(n=min(n, len(pool)), random_state=seed)
    a[["id", "objeto"]].assign(rotulo="").to_csv(ARQ_CEGO, index=False, **CSV)
    print(GUIA); print(f"\n{len(a)} contratos para rotular SEM ver sugestão em: {ARQ_CEGO}")

def _kappa(a, b):
    a, b = np.asarray(a), np.asarray(b); cats = sorted(set(a) | set(b)); n = len(a)
    po = (a == b).mean(); pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return float((po - pe) / (1 - pe)) if pe < 1 else float("nan")

def _ic_kappa(a, b, B=2000, seed=3):
    rng = np.random.default_rng(seed); a, b = np.asarray(a), np.asarray(b); ks = []
    for _ in range(B):
        i = rng.integers(0, len(a), len(a)); ks.append(_kappa(a[i], b[i]))
    ks = [k for k in ks if np.isfinite(k)]
    return (float(np.percentile(ks, 2.5)), float(np.percentile(ks, 97.5))) if ks else (float("nan"), float("nan"))

def kappa():
    """compara o rótulo cego da autora com (1) o rótulo do llm e (2) a categoria do classificador por palavras-chave."""
    h = _ler(ARQ_CEGO); h = h[h["rotulo"].fillna("").str.strip().ne("")].copy()
    if not len(h): raise SystemExit(f"Preencha a coluna rotulo em {ARQ_CEGO} primeiro.")
    h["humano"] = h["rotulo"].str.strip().str.upper()
    c = _ler(os.path.join(DATA, "rotulos_llm.csv")); g = _ler(GAB)
    d = h.merge(c[["id", "rotulo_llm"]], on="id").merge(g[["id", "categoria_auto"]], on="id")
    d["llm"] = d["rotulo_llm"].str.strip().str.upper()
    print(f"n = {len(d)} contratos rotulados às cegas pela autora\n")
    for nome, col in [("LLM", "llm"), ("Classificador por palavras-chave", "categoria_auto")]:
        k = int((d[col] == d["humano"]).sum()); lo, hi = wilson(k, len(d)); kp = _kappa(d[col], d["humano"]); kl, ku = _ic_kappa(d[col], d["humano"])
        print(f"{nome} vs humano: acurácia {k}/{len(d)} = {100*k/len(d):.1f}% (IC95% Wilson {100*lo:.1f}-{100*hi:.1f}%) | kappa de Cohen {kp:.2f} (IC95% bootstrap {kl:.2f} a {ku:.2f})")
        print(pd.crosstab(d[col], d["humano"], rownames=[nome], colnames=["humano"]).to_string(), "\n")
    print("Kappa: <0,40 fraco | 0,40-0,60 moderado | 0,60-0,80 substancial | >0,80 quase perfeito (Landis & Koch).")

def _recall(peso, auto, true):
    den = peso[true].sum()
    return float(peso[auto & true].sum() / den) if den > 0 else float("nan")

def _recall_ic(peso, auto, true, grupos, boot, rng):
    vals = []
    for _ in range(boot):
        ix = np.concatenate([rng.choice(g, size=len(g)) for g in grupos])
        den = peso[ix][true[ix]].sum()
        if den > 0: vals.append(peso[ix][auto[ix] & true[ix]].sum() / den)
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if len(vals) >= boot * 0.5 else (float("nan"), float("nan"))

def calcular(d: pd.DataFrame, pops: dict, boot=1000, seed=1):
    """d: id, estrato, categoria_auto, rotulo (já validados). retorna dict por categoria + 'ti (binário)'."""
    est = d.groupby("estrato").size()
    peso = d["estrato"].map(lambda e: pops[e] / est[e]).to_numpy(float)
    auto, rot = d["categoria_auto"].to_numpy(), d["rotulo"].to_numpy()
    grupos = [np.where(d["estrato"].to_numpy() == e)[0] for e in est.index]
    rng = np.random.default_rng(seed); res = {}
    def um(nome, a_mask, t_mask, est_precisao):
        sel = d["estrato"].isin(est_precisao).to_numpy() & a_mask
        k, n = int((t_mask & sel).sum()), int(sel.sum())
        lo, hi = wilson(k, n)
        w = peso[sel]; prec = float((w * t_mask[sel]).sum() / w.sum()) if n else float("nan")
        r_lo, r_hi = _recall_ic(peso, a_mask, t_mask, grupos, boot, rng) if boot else (float("nan"),) * 2
        res[nome] = dict(n_auto=n, precisao=prec, p_lo=lo if len(est_precisao) == 1 else float("nan"),
                         p_hi=hi if len(est_precisao) == 1 else float("nan"),
                         recall=_recall(peso, a_mask, t_mask), r_lo=r_lo, r_hi=r_hi, positivos_reais=int(t_mask.sum()))
    for c in CATS:
        um(c, auto == c, rot == c, [c])
    um("TI (qualquer)", np.isin(auto, CATS), np.isin(rot, CATS), CATS)
    return res

def _ler(caminho):
    """lê o csv com ';' (excel em português) ou ',' (google sheets exporta com vírgula)."""
    d = pd.read_csv(caminho, dtype=str, **CSV)
    if len(d.columns) == 1:
        d = pd.read_csv(caminho, dtype=str, sep=",", encoding="utf-8-sig")
    return d

def medir(boot=1000):
    r = _ler(ARQ); g = _ler(GAB)
    meta = json.load(open(META))
    d = r.merge(g, on="id"); d["rotulo"] = d["rotulo"].fillna("").str.strip().str.upper()
    invalidos = d[~d["rotulo"].isin(VALIDOS)]
    if len(invalidos):
        print(f"ATENÇÃO: {len(invalidos)} linhas sem rótulo válido foram ignoradas (valores aceitos: {', '.join(VALIDOS)}).")
        d = d[d["rotulo"].isin(VALIDOS)]
    if d.empty: raise SystemExit("Nenhum rótulo preenchido ainda.")
    print("Matriz de confusão (linhas = categoria automática; colunas = rótulo manual; contagem simples):")
    print(pd.crosstab(d["categoria_auto"], d["rotulo"]).to_string(), "\n")
    res = calcular(d.reset_index(drop=True), meta["populacao"], boot)
    pct = lambda x: "  n/d " if pd.isna(x) else f"{100 * x:5.1f}%"
    print(f"{'categoria':<15}{'n_auto':>7}  {'precisão':>9}  {'IC95% prec.':>16}  {'revocação':>9}  {'IC95% revoc.':>16}  positivos_reais")
    for k, v in res.items():
        print(f"{k:<15}{v['n_auto']:>7}  {pct(v['precisao']):>9}  [{pct(v['p_lo'])},{pct(v['p_hi'])}]  {pct(v['recall']):>9}  [{pct(v['r_lo'])},{pct(v['r_hi'])}]  {v['positivos_reais']}")
    pd.DataFrame(res).T.to_csv(os.path.join(DATA, "rotulagem_resultado.csv"), **CSV)
    print("\nRevocação é estimada (com pesos) e tem IC largo se houver poucos positivos reais entre os descartados.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("export"); e.add_argument("--n", type=int, default=30)
    e.add_argument("--n-descartados", type=int, default=120); e.add_argument("--forcar", action="store_true")
    e.add_argument("--n-nuvem-ia", type=int, default=None, help="tamanho da amostra só de NUVEM e IA (padrão: igual a --n)")
    sp.add_parser("medir")
    v = sp.add_parser("revisar"); v.add_argument("--frac", type=float, default=0.15)
    ce = sp.add_parser("cego"); ce.add_argument("--n", type=int, default=60)
    sp.add_parser("kappa")
    a = ap.parse_args()
    (exportar(a.n, a.n_descartados, a.forcar, n_nuvem_ia=a.n_nuvem_ia) if a.cmd == "export"
     else revisar(a.frac) if a.cmd == "revisar" else cego(a.n) if a.cmd == "cego" else kappa() if a.cmd == "kappa" else medir())
