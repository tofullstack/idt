import sys, json
from datetime import date
from collectors import compras
from normalize import auditar_compras

fonte, orgao = sys.argv[1], sys.argv[2]
ano = int(sys.argv[3]) if len(sys.argv) > 3 else 2024
assert fonte == "compras", "sample só implementado para compras (Transparência: use o Swagger)"
for c in compras.contratos(orgao, date(ano, 1, 1), date(ano, 12, 31)):
    n, problemas, candidatos = auditar_compras(c, orgao)
    print("=== REGISTRO BRUTO ==="); print(json.dumps(c, indent=2, ensure_ascii=False))
    print("\n=== NORMALIZADO ==="); print(json.dumps(n, indent=2, ensure_ascii=False))
    print("\n=== CAMPOS CANDIDATOS (valor/data/fornecedor/objeto/id) ==="); print(json.dumps(candidatos, indent=2, ensure_ascii=False))
    print("\n=== PROBLEMAS ===" if problemas else "\nOK: todos os campos essenciais foram preenchidos.")
    for p in problemas: print(" -", p)
    break
else:
    print("Nenhum contrato retornado para esse órgão/ano.")
