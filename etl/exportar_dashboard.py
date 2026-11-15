import json, math, os
from datetime import datetime
import numpy as np
import pandas as pd
import analise as A

DESTINO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "public", "data")


def _limpa(o):
    if isinstance(o, dict): return {str(k): _limpa(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_limpa(v) for v in o]
    if isinstance(o, (np.bool_, bool)): return bool(o)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)): return float(o) if math.isfinite(o) else None
    return o


def _registros(df):
    return _limpa(df.to_dict(orient="records"))


def _versao(c):
    """todas as tabelas do painel para um conjunto de contratos (com ou sem estatais)."""
    idt_m = A.idt_serie(c)
    idt_b = A.idt_serie(c, mensal=False).iloc[0]
    m = A.serie_mensal(c)
    top, hhi = A.concentracao(c)
    out = dict(
        idt_bienio=_limpa(idt_b.to_dict()),
        idt_mensal=_registros(idt_m),
        categorias=_registros(A.tabela_categoria(c)),
        serie_mensal=_registros(m),
        concentracao=dict(hhi=_limpa(hhi), top3_pct=_limpa(float(top.pct_do_valor_nuvem_ia.head(3).sum())),
                          top=_registros(top)),
        anpd=None,
    )
    r = A.cruzar_anpd(m)
    if r:
        d, corr = r
        d = d.merge(idt_m[["mes", "idt"]], on="mes", how="left")
        out["anpd"] = dict(serie=_registros(d[["mes", "incidentes_publico", "idt", "pct_B_tic", "pct_B_ou_C_nuvem_ia", "valor_tic"]]),
                           correlacoes=_registros(corr))
    return out


def montar_dados(c, est, sintetico=False):
    fam = c.categoria.isin(A.FAMILIA)
    meta = dict(
        gerado_em=datetime.now().isoformat(timespec="seconds"),
        janela=list(A.JANELA), contratos_janela=int(len(c)), contratos_familia_tic=int(fam.sum()),
        estatais=dict(contratos=int((est & fam).sum()), valor=float(c.loc[est & fam, "valor"].sum()),
                      pct_valor_tic=float(100 * c.loc[est & fam, "valor"].sum() / c.loc[fam, "valor"].sum())),
        cenarios_w=A.CENARIOS_W, sintetico=bool(sintetico),
    )
    return _limpa(dict(meta=meta, versoes={"com_estatais": _versao(c), "sem_estatais": _versao(c[~est])}))


def gravar(dados, pasta=DESTINO):
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, "dados.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    return caminho


if __name__ == "__main__":
    c = A.carregar()
    est = c.fornecedor_cnpj.astype(str).str[:8].isin(A.ESTATAIS) & c.categoria.isin(A.FAMILIA)
    print("gravado:", gravar(montar_dados(c, est)))
