import json, sys
from datetime import date
import normalize

def resumo(brutos, orgao):
    ids = [normalize.de_compras(c, orgao)["id"] for c in brutos]
    linhas = [json.dumps(c, sort_keys=True, default=str) for c in brutos]
    return dict(linhas=len(brutos), ids_distintos=len(set(ids)), linhas_identicas_repetidas=len(linhas) - len(set(linhas)), ids=set(ids))

def comparar(a, b):
    return sorted(a["ids"] - b["ids"]), sorted(b["ids"] - a["ids"])

if __name__ == "__main__":
    from collectors import compras
    _, orgao, ano = sys.argv[1], sys.argv[2], int(sys.argv[3])
    A = resumo(list(compras.contratos(orgao, date(ano, 1, 1), date(ano, 12, 31), tamanho=500)), orgao)
    B = resumo(list(compras.contratos(orgao, date(ano, 1, 1), date(ano, 12, 31), tamanho=100)), orgao)
    for nome, r in (("páginas de 500", A), ("páginas de 100", B)):
        print(f"{nome}: linhas={r['linhas']} ids_distintos={r['ids_distintos']} linhas_identicas_repetidas={r['linhas_identicas_repetidas']}")
    so_a, so_b = comparar(A, B)
    print(f"ids só no conjunto de 500: {len(so_a)} | só no de 100: {len(so_b)}")
    if not so_a and not so_b:
        print("-> ESTÁVEL: os dois conjuntos têm os mesmos ids. As repetições vêm da própria API; deduplicar basta.")
    else:
        print("-> INSTÁVEL: a paginação perde/repete linhas. Exemplos:", (so_a + so_b)[:5])
