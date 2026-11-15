import os, sys
import numpy as np
import pandas as pd
import db
from enrich import marca_hyperscaler, intermediacao_nuvem

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saida")
JANELA = ("2024-01", "2025-12")
FAMILIA = ["NUVEM", "IA", "INFRA", "TIC"]
ESTATAIS = {"33683111", "42422253", "00336701"}
CENARIOS_W = {"W1_hyperscaler_pesa_mais": {"A": 1.5, "B_so": 1.0, "C_so": 1.0},
              "W2_indireta_pesa_menos":   {"A": 1.0, "B_so": 1.0, "C_so": 0.5}}


def carregar():
    conn = db.connect(); db.init_schema(conn)
    c = pd.read_sql("""SELECT c.id, c.orgao, c.fornecedor_cnpj, c.objeto, c.valor, c.data_inicio, c.data_fim, c.categoria,
                              f.razao_social, f.origem, f.hyperscaler
                       FROM contrato c JOIN fornecedor f ON f.cnpj = c.fornecedor_cnpj""", conn)
    conn.close()
    c["valor"] = c["valor"].astype(float)
    c["data_inicio"] = pd.to_datetime(c["data_inicio"], errors="coerce")
    c["data_fim"] = pd.to_datetime(c["data_fim"], errors="coerce")
    c = c[c["data_inicio"].notna()].copy()
    c["mes"] = c["data_inicio"].dt.to_period("M").astype(str)
    c = c[(c["mes"] >= JANELA[0]) & (c["mes"] <= JANELA[1])].copy()
    c["A"] = c["hyperscaler"].astype(bool)
    c["B"] = c["origem"].eq("ESTRANGEIRO")
    marca = c["objeto"].map(marca_hyperscaler) | c["objeto"].map(intermediacao_nuvem)
    c["C"] = marca & ~c["B"]
    return c


def tabela_categoria(c):
    linhas = []
    for cat in FAMILIA + ["NUVEM+IA", "TIC (família completa)"]:
        if cat == "NUVEM+IA":
            d = c[c.categoria.isin(["NUVEM", "IA"])]
        elif cat.startswith("TIC ("):
            d = c[c.categoria.isin(FAMILIA)]
        else:
            d = c[c.categoria == cat]
        tot = d.valor.sum()
        linhas.append(dict(categoria=cat, contratos=len(d), valor_total=tot, mediana_contrato=d.valor.median(),
                           media_contrato=d.valor.mean(), maximo=d.valor.max(),
                           pct_valor_A=100 * d.loc[d.A, "valor"].sum() / tot if tot else np.nan,
                           pct_valor_B=100 * d.loc[d.B, "valor"].sum() / tot if tot else np.nan,
                           pct_valor_C=100 * d.loc[d.C, "valor"].sum() / tot if tot else np.nan,
                           pct_valor_B_ou_C=100 * d.loc[d.B | d.C, "valor"].sum() / tot if tot else np.nan,
                           pct_indeterminado=100 * d.loc[d.origem.eq("INDETERMINADO"), "valor"].sum() / tot if tot else np.nan))
    return pd.DataFrame(linhas)


def expandir_proporcional(c):
    """sensibilidade: em vez de alocar o valor global todo no mês de início, dilui igualmente pelos meses de vigência
    (data_inicio..data_fim; sem data_fim válida, fica só no mês de início) e mantém só os meses dentro da janela.
    o valor fora da janela é descartado, então a soma pode ficar abaixo do valor global."""
    linhas = []
    for r in c.itertuples():
        ini = r.data_inicio.to_period("M"); fim = r.data_fim.to_period("M") if pd.notna(r.data_fim) and r.data_fim >= r.data_inicio else ini
        ms = pd.period_range(ini, fim, freq="M"); parte = r.valor / len(ms)
        for m in ms:
            if JANELA[0] <= str(m) <= JANELA[1]:
                linhas.append((r.Index, str(m), parte))
    e = pd.DataFrame(linhas, columns=["idx", "mes", "valor_parte"]).set_index("idx")
    out = c.drop(columns=["mes", "valor"]).join(e, how="inner").rename(columns={"valor_parte": "valor"})
    return out


def serie_mensal(c):
    meses = pd.period_range(*JANELA, freq="M").astype(str)
    f = c[c.categoria.isin(FAMILIA)]
    g = pd.DataFrame(index=meses)
    g["contratos_tic"] = f.groupby("mes").size()
    g["valor_tic"] = f.groupby("mes").valor.sum()
    g["valor_B"] = f[f.B].groupby("mes").valor.sum()
    g["valor_C"] = f[f.C].groupby("mes").valor.sum()
    n = c[c.categoria.isin(["NUVEM", "IA"])]
    g["valor_nuvem_ia"] = n.groupby("mes").valor.sum()
    g["valor_nuvem_ia_B_ou_C"] = n[n.B | n.C].groupby("mes").valor.sum()
    g = g.fillna(0)
    g["pct_B_tic"] = 100 * g.valor_B / g.valor_tic.replace(0, np.nan)
    g["pct_B_ou_C_nuvem_ia"] = 100 * g.valor_nuvem_ia_B_ou_C / g.valor_nuvem_ia.replace(0, np.nan)
    g.index.name = "mes"
    return g.reset_index()


def peso_cenario(c, pesos):
    """peso por contrato: a > b_so > c_so (classes exclusivas); contrato não dependente tem peso 0."""
    w = np.zeros(len(c))
    w = np.where(c["C"] & ~c["A"] & ~c["B"], pesos["C_so"], w)
    w = np.where(c["B"] & ~c["A"], pesos["B_so"], w)
    w = np.where(c["A"], pesos["A"], w)
    return pd.Series(w, index=c.index)


def idt_serie(c, mensal=True):
    """idt = 100 * valor dependente / valor total da família tic (nuvem+ia+infra+tic).
    dependente = b ou c (sócio estrangeiro na cadeia societária, ou marca/intermediação de hyperscaler via fornecedor nacional; a está em b).
    mesmo critério em toda a análise. colunas idt_w1/idt_w2: sensibilidade com peso (não é percentual puro; pode passar de 100 só se pesos > 1)."""
    f = c[c.categoria.isin(FAMILIA)].copy()
    f["dep"] = f.B | f.C
    for nome, pesos in CENARIOS_W.items():
        f[nome] = peso_cenario(f, pesos) * f.valor
    f["valor_dep"] = np.where(f.dep, f.valor, 0.0)
    def resumo(g):
        tot = g.valor.sum()
        out = dict(contratos=len(g), valor_tic=tot, valor_dep=g.valor_dep.sum(),
                   idt=100 * g.valor_dep.sum() / tot if tot else np.nan)
        for nome in CENARIOS_W: out["idt_" + nome[:2]] = 100 * g[nome].sum() / tot if tot else np.nan
        return pd.Series(out)
    if not mensal:
        return resumo(f).to_frame().T
    meses = pd.period_range(*JANELA, freq="M").astype(str)
    g = f.groupby("mes").apply(resumo, include_groups=False).reindex(meses)
    g.index.name = "mes"
    g[["contratos", "valor_tic", "valor_dep"]] = g[["contratos", "valor_tic", "valor_dep"]].fillna(0)
    return g.reset_index()


def idt_tabelas(c, est):
    """idt mensal e agregado do biênio, com e sem estatais (est = máscara booleana das estatais, alinhada a c)."""
    m_com, m_sem = idt_serie(c), idt_serie(c[~est])
    b = pd.concat([idt_serie(c, mensal=False).assign(versao="com estatais"),
                   idt_serie(c[~est], mensal=False).assign(versao="sem estatais")], ignore_index=True)
    m = m_com.merge(m_sem, on="mes", suffixes=("_com_estatais", "_sem_estatais"))
    return m, b[["versao", "contratos", "valor_tic", "valor_dep", "idt", "idt_W1", "idt_W2"]]


def concentracao(c):
    n = c[c.categoria.isin(["NUVEM", "IA"])]
    t = n.groupby("razao_social").valor.sum().sort_values(ascending=False)
    top = (t / t.sum() * 100).head(10).rename("pct_do_valor_nuvem_ia").reset_index()
    return top, float(((t / t.sum()) ** 2).sum() * 10000)


def descritiva(x):
    x = pd.Series(x).dropna()
    return dict(n=len(x), media=x.mean(), desvio=x.std(ddof=1), minimo=x.min(), mediana=x.median(), maximo=x.max())


def ic_rho(r, n, conf=0.95):
    """ic de fisher (z = arctanh r, erro 1/sqrt(n-3)) para a correlação. supõe observações independentes:
    com séries temporais autocorrelacionadas o ic verdadeiro é mais largo (tratar como limite inferior da incerteza)."""
    from scipy import stats
    if n is None or n < 5 or not np.isfinite(r): return (np.nan, np.nan)
    z, se = np.arctanh(np.clip(r, -0.9999, 0.9999)), 1 / np.sqrt(n - 3)
    k = stats.norm.ppf(0.5 + conf / 2)
    return (float(np.tanh(z - k * se)), float(np.tanh(z + k * se)))


def cruzar_anpd(m):
    caminho = os.path.join(SAIDA, "anpd_mensal.csv")
    if not os.path.exists(caminho):
        pd.DataFrame({"mes": m["mes"], "incidentes_publico": ""}).to_csv(caminho, index=False)
        print(f"\nANPD: modelo criado em {caminho}. Preencha incidentes_publico (24 meses) e rode de novo.")
        return None
    a = pd.read_csv(caminho)
    a["incidentes_publico"] = pd.to_numeric(a["incidentes_publico"], errors="coerce")
    d = m.merge(a, on="mes", how="left")
    if d["incidentes_publico"].notna().sum() < 6:
        print("\nANPD: arquivo ainda sem valores suficientes."); return None
    from scipy import stats
    linhas = []
    for nome, col in [("pct_B_tic", "pct_B_tic"), ("pct_B_ou_C_nuvem_ia", "pct_B_ou_C_nuvem_ia"), ("valor_tic", "valor_tic")]:
        for lag in range(0, 4):
            x = d[col].shift(lag); y = d["incidentes_publico"]
            ok = x.notna() & y.notna()
            if ok.sum() < 6: continue
            r, p = stats.spearmanr(x[ok], y[ok])
            dx, dy = x.diff(), y.diff(); ok2 = dx.notna() & dy.notna()
            r2, p2 = stats.spearmanr(dx[ok2], dy[ok2]) if ok2.sum() >= 6 else (np.nan, np.nan)
            n1, n2 = int(ok.sum()), int(ok2.sum())
            l1, u1 = ic_rho(r, n1); l2, u2 = ic_rho(r2, n2)
            linhas.append(dict(serie=nome, defasagem_meses=lag, n=n1, rho=r, ic95_inf=l1, ic95_sup=u1, p=p,
                               n_dif=n2, rho_dif=r2, ic95_dif_inf=l2, ic95_dif_sup=u2, p_dif=p2))
    return d, pd.DataFrame(linhas)


def tendencia(d):
    """diagnóstico de tendência: spearman de cada série contra o tempo. séries com tendência comum geram correlação espúria nos níveis."""
    from scipy import stats
    t = np.arange(len(d)); linhas = []
    for col in ["incidentes_publico", "valor_tic", "pct_B_tic", "pct_B_ou_C_nuvem_ia"]:
        ok = d[col].notna()
        r, p = stats.spearmanr(t[ok], d.loc[ok, col]); lo, hi = ic_rho(r, int(ok.sum()))
        linhas.append(dict(serie=col, n=int(ok.sum()), rho_com_tempo=r, ic95_inf=lo, ic95_sup=hi, p=p))
    return pd.DataFrame(linhas)


def figuras(cat, m, d):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.5))
    t = cat[cat.categoria.isin(FAMILIA + ["NUVEM+IA"])]
    x = np.arange(len(t)); w = 0.27
    for k, (col, rot) in enumerate([("pct_valor_A", "A: hyperscaler"), ("pct_valor_B", "B: sócio estrangeiro"),
                                    ("pct_valor_C", "C: marca via fornecedor nacional")]):
        ax.bar(x + (k - 1) * w, t[col], w, label=rot)
    ax.set_xticks(x); ax.set_xticklabels(t.categoria); ax.set_ylabel("% do valor contratado")
    ax.set_title("Participação de valor por definição de dependência (2024-2025)"); ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False); fig.tight_layout()
    fig.savefig(os.path.join(SAIDA, "fig1_categoria_definicoes.png"), dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(m["mes"], m["pct_B_tic"], marker="o", label="% estrangeiro (B) no gasto de TIC")
    ax.plot(m["mes"], m["pct_B_ou_C_nuvem_ia"], marker="s", label="% B ou C em nuvem/IA")
    ax.set_xticks(range(0, len(m), 3)); ax.set_xticklabels(m["mes"][::3], rotation=45)
    ax.set_ylabel("%"); ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Série mensal (valor por mês de início do contrato)"); fig.tight_layout()
    fig.savefig(os.path.join(SAIDA, "fig2_serie_mensal.png"), dpi=160); plt.close(fig)

    if d is not None:
        fig, ax = plt.subplots(figsize=(9, 4.5)); ax2 = ax.twinx()
        ax.plot(d["mes"], d["pct_B_ou_C_nuvem_ia"], color="#1f77b4", marker="o", label="% B ou C em nuvem/IA")
        ax2.bar(d["mes"], d["incidentes_publico"], alpha=0.3, color="#d62728", label="Incidentes (setor público, ANPD)")
        ax.set_xticks(range(0, len(d), 3)); ax.set_xticklabels(d["mes"][::3], rotation=45)
        ax.set_ylabel("% do valor"); ax2.set_ylabel("incidentes/mês")
        ax.set_title("Contratação de nuvem/IA e incidentes notificados (agregado nacional)")
        fig.tight_layout(); fig.savefig(os.path.join(SAIDA, "fig3_anpd.png"), dpi=160); plt.close(fig)


def maiores(c, n=8):
    t = c[c.categoria.isin(FAMILIA)].nlargest(n, "valor")
    return t[["valor", "categoria", "razao_social", "mes", "objeto"]].assign(objeto=lambda d: d.objeto.str.slice(0, 110))


def main():
    os.makedirs(SAIDA, exist_ok=True)
    c = carregar()
    if "--excluir-acima" in sys.argv:
        lim = float(sys.argv[sys.argv.index("--excluir-acima") + 1])
        antes = len(c); c = c[c.valor <= lim].copy()
        print(f"SENSIBILIDADE: excluídos {antes - len(c)} contrato(s) acima de R$ {lim:,.0f}")
    est = c.fornecedor_cnpj.astype(str).str[:8].isin(ESTATAIS) & c.categoria.isin(FAMILIA)
    tot_fam = c.loc[c.categoria.isin(FAMILIA), "valor"].sum()
    print(f"ESTATAIS DE TIC (Serpro/Dataprev/Telebras): {int(est.sum())} contratos, R$ {c.loc[est, 'valor'].sum():,.0f} "
          f"= {100 * c.loc[est, 'valor'].sum() / tot_fam:.1f}% do valor da família TIC")
    c0, est0 = c.copy(), est.copy()
    if "--sem-estatais" in sys.argv:
        c = c[~est].copy(); print("SENSIBILIDADE: contratos com Serpro/Dataprev/Telebras excluídos")
    print("\n== T0: maiores contratos da família TIC (confira se são mesmo o que a categoria diz) ==")
    pd.set_option("display.max_colwidth", 115)
    print(maiores(c).to_string(index=False))
    print(f"{len(c)} contratos na janela {JANELA[0]}..{JANELA[1]}; categorias da família TIC: {c.categoria.isin(FAMILIA).sum()}")
    cat = tabela_categoria(c); cat.to_csv(os.path.join(SAIDA, "t1_categoria_definicoes.csv"), index=False)
    pd.set_option("display.width", 220); pd.set_option("display.float_format", lambda v: f"{v:,.1f}")
    print("\n== T1: categoria x definição (A hyperscaler | B sócio estrangeiro | C marca via nacional) ==")
    print(cat.to_string(index=False))
    PROP = "--proporcional" in sys.argv
    SUF = "_proporcional" if PROP else ""
    if PROP: print("\nSENSIBILIDADE PROPORCIONAL: valor diluído pelos meses de vigência (séries mensais T2 e T4; T1 e T3 seguem o valor global)")
    m = serie_mensal(expandir_proporcional(c) if PROP else c)
    if "--burnin" in sys.argv:
        nb = int(sys.argv[sys.argv.index("--burnin") + 1]); m = m.iloc[nb:].reset_index(drop=True); SUF += f"_burnin{nb}"
        print(f"\nBURN-IN: primeiros {nb} meses descartados; séries mensais de {m.mes.iloc[0]} a {m.mes.iloc[-1]} (n = {len(m)})")
    m.to_csv(os.path.join(SAIDA, f"t2_serie_mensal{SUF}.csv"), index=False)
    print("\n== T2: estatísticas descritivas das séries mensais (n = 24 meses) ==")
    print(pd.DataFrame({k: descritiva(m[k]) for k in ["valor_tic", "pct_B_tic", "valor_nuvem_ia", "pct_B_ou_C_nuvem_ia"]}).T.to_string())
    if not PROP:
        try:
            im, ib = idt_tabelas(c0, est0)
            im.to_csv(os.path.join(SAIDA, f"t6_idt_mensal{SUF}.csv"), index=False); ib.to_csv(os.path.join(SAIDA, f"t7_idt_bienio{SUF}.csv"), index=False)
            print("\n== T7: IDT agregado do biênio = 100 x valor dependente (B ou C) / valor total da família TIC ==")
            print(ib.to_string(index=False, float_format=lambda v: f"{v:,.1f}"))
            r = pd.DataFrame({k: descritiva(im[f"idt_{k}"]) for k in ("com_estatais", "sem_estatais")}).T
            print("\n== T6: IDT mensal (oscila muito: contratos grandes caem inteiros no mês de início; use o agregado como leitura principal) ==")
            print(r.to_string(float_format=lambda v: f"{v:,.1f}"))
            print(f"IDT = valor dependente / valor TIC; W1 (hyperscaler 1,5) e W2 (indireta 0,5) são cenários de sensibilidade, sem calibração.")
        except Exception as e:
            print(f"\n(IDT não calculado: {e})")
    top, hhi = concentracao(c); top.to_csv(os.path.join(SAIDA, "t3_concentracao_nuvem_ia.csv"), index=False)
    print(f"\n== T3: maiores fornecedores de nuvem/IA (HHI = {hhi:,.0f}; 3 maiores = {top.pct_do_valor_nuvem_ia.head(3).sum():.1f}% do valor) ==\n{top.to_string(index=False)}")
    r = cruzar_anpd(m); d = None
    if r:
        d, corr = r
        corr.to_csv(os.path.join(SAIDA, f"t4_correlacoes_anpd{SUF}.csv"), index=False)
        d.to_csv(os.path.join(SAIDA, f"t5_cruzamento_mensal{SUF}.csv"), index=False)
        print("\n== T4: Spearman entre séries agregadas e incidentes do setor público (EXPLORATÓRIO, sem causalidade) ==")
        print(corr.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        print("\n== Diagnóstico de tendência: Spearman de cada série contra o tempo (|rho| alto = tendência; correlação nos níveis pode ser espúria) ==")
        print(tendencia(d).to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        print("IC 95% de Fisher (assume independência; séries autocorrelacionadas têm IC mais largo). "
              "Com n=24 o teste só detecta |rho| >= ~0,55 com 80% de poder (|rho|=0,4: ~49%).")
    figuras(cat, m, d)
    if not PROP and "--burnin" not in sys.argv:
        try:
            import exportar_dashboard as ED
            print(f"\nDashboard: dados gravados em {ED.gravar(ED.montar_dados(c0, est0))}")
        except Exception as e:
            print(f"\n(dashboard: dados não exportados: {e})")
    print(f"\nArquivos gravados em {SAIDA}")


if __name__ == "__main__":
    main()
