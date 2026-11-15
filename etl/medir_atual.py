import pandas as pd
import db
import rotular as R

CATS = ["NUVEM", "IA", "INFRA", "TIC"]


def precisao_atual(rot, atual):
    """rot: dataframe id, rotulo (humano). atual: dataframe id, categoria (regras atuais). precisão por categoria atual."""
    d = rot.merge(atual, on="id")
    linhas = []
    for cat in CATS:
        x = d[d["categoria"] == cat]; k = int((x["rotulo"] == cat).sum()); n = len(x)
        lo, hi = R.wilson(k, n) if n else (float("nan"), float("nan"))
        linhas.append(dict(categoria=cat, n_atual=n, acertos=k, precisao=100 * k / n if n else float("nan"), ic_inf=100 * lo, ic_sup=100 * hi))
    return pd.DataFrame(linhas)


def main():
    r = R._ler(R.ARQ); r["rotulo"] = r["rotulo"].fillna("").str.strip().str.upper()
    r = r[r["rotulo"].isin(R.VALIDOS)][["id", "rotulo"]]
    conn = db.connect(); atual = pd.read_sql("SELECT id, categoria FROM contrato", conn); conn.close()
    r["id"] = r["id"].astype(str); atual["id"] = atual["id"].astype(str)
    t = precisao_atual(r, atual)
    pd.set_option("display.width", 160)
    print("Precisão das regras atuais na amostra rotulada (otimista: regras ajustadas nesta amostra)\n")
    print(t.to_string(index=False, float_format=lambda v: f"{v:.1f}"))


if __name__ == "__main__":
    main()
