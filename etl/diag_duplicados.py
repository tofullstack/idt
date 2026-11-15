import json, sys
from datetime import date
import normalize
from enrich import categoria

def duplicados(brutos, orgao, todas=False):
    grupos = {}
    for c in brutos:
        n = normalize.de_compras(c, orgao)
        if not todas and categoria(n["objeto"]) == "OUTRO":
            continue
        grupos.setdefault(n["id"], []).append(c)
    return {k: v for k, v in grupos.items() if len(v) > 1}, sum(len(v) for v in grupos.values())

def diferencas(rows):
    chaves = set().union(*[r.keys() for r in rows])
    return {k: [r.get(k) for r in rows] for k in sorted(chaves)
            if len({json.dumps(r.get(k), default=str) for r in rows}) > 1}

if __name__ == "__main__":
    import coleta_compras as compras
    fonte, orgao, ano = sys.argv[1], sys.argv[2], int(sys.argv[3])
    dups, total_ti = duplicados(compras.contratos(orgao, date(ano, 1, 1), date(ano, 12, 31)), orgao, todas="--todas" in sys.argv)
    extras = sum(len(v) - 1 for v in dups.values())
    print(f"linhas de TI: {total_ti} | ids repetidos: {len(dups)} | linhas excedentes: {extras}")
    for k, rows in list(dups.items())[:8]:
        print(f"\n--- {k} ({len(rows)} linhas) --- campos que DIFEREM:")
        print(json.dumps(diferencas(rows), indent=1, ensure_ascii=False, default=str)[:1500])
