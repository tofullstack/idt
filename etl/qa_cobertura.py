import calendar, os, random, sys
from datetime import date
import pandas as pd
import coleta_compras as cc
import normalize

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def _ids(rows, orgao, ano):
    return {normalize.de_compras(c, orgao)["id"] for c in rows if str(c.get("dataVigenciaInicial"))[:4] == str(ano)}

def ids_adaptativo(orgao, ano):
    return _ids(cc.contratos(orgao, date(ano, 1, 1), date(ano, 12, 31)), orgao, ano)

def ids_mensal(orgao, ano):
    out = set()
    for m in range(1, 13):
        a, b = date(ano, m, 1), date(ano, m, calendar.monthrange(ano, m)[1])
        out |= _ids(cc._janela(orgao, a, b, cc.TAMANHO), orgao, ano)
    return out

def comparar(A, B):
    return dict(adaptativo=len(A), mensal=len(B), em_ambos=len(A & B), so_adaptativo=len(A - B), so_mensal=len(B - A))

def main(orgaos, ano):
    linhas = []
    for o in orgaos:
        r = comparar(ids_adaptativo(o, ano), ids_mensal(o, ano)); r["orgao"] = o; linhas.append(r)
        print(f"{o}: adaptativo={r['adaptativo']} mensal={r['mensal']} só_adaptativo={r['so_adaptativo']} só_mensal={r['so_mensal']}", flush=True)
    df = pd.DataFrame(linhas)
    uniao = (df.em_ambos + df.so_adaptativo + df.so_mensal).sum()
    print(f"\nconcordância global: {df.em_ambos.sum()} de {uniao} ids = {100 * df.em_ambos.sum() / max(uniao, 1):.2f}%")

if __name__ == "__main__":
    if sys.argv[1] == "--amostra":
        n, ano = int(sys.argv[2]), int(sys.argv[3])
        lista = pd.read_csv(os.path.join(DATA, "orgaos_validados.csv"), dtype=str).codigo_orgao.tolist()
        orgaos = random.Random(7).sample(lista, min(n, len(lista)))
    else:
        orgaos, ano = [sys.argv[1]], int(sys.argv[2])
    main(orgaos, ano)
