import argparse, json, re
import db
from classifier import _consulta, classificar, ConsultaFalhou

CAMPOS = ("razao_social", "natureza_juridica", "codigo_natureza_juridica", "capital_social", "porte",
          "pais", "codigo_pais", "situacao_cadastral")

def mostrar(cnpj, nome=""):
    cnpj = re.sub(r"\D", "", cnpj)
    print("=" * 100); print(f"{cnpj}  {nome}")
    try:
        d = _consulta(cnpj)
    except ConsultaFalhou as e:
        print(f"  FALHA NA CONSULTA: {e}"); return
    if not d:
        print("  404: CNPJ não encontrado na BrasilAPI"); return
    for k in CAMPOS:
        if k in d: print(f"  {k}: {d[k]}")
    qsa = d.get("qsa") or []
    print(f"  QSA ({len(qsa)} sócios/administradores):")
    for s in qsa[:15]:
        print("   ", json.dumps(s, ensure_ascii=False))
    if len(qsa) > 15: print(f"    ... +{len(qsa) - 15}")
    print("  VEREDITO:", classificar(cnpj, nome))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nomes", nargs="*", help="trechos do nome (case-insensitive)")
    ap.add_argument("--cnpj", help="consulta direta por CNPJ")
    ap.add_argument("--max", type=int, default=3, help="máx. fornecedores por trecho de nome")
    a = ap.parse_args()
    if a.cnpj:
        mostrar(a.cnpj)
    if a.nomes:
        conn = db.connect()
        for n in a.nomes:
            rows = db.executar(conn, """SELECT f.cnpj, f.razao_social, f.origem, ROUND(SUM(c.valor)) AS v
                FROM fornecedor f JOIN contrato c ON c.fornecedor_cnpj=f.cnpj
                WHERE UPPER(f.razao_social) LIKE %s AND LENGTH(f.cnpj)=14
                GROUP BY f.cnpj, f.razao_social, f.origem ORDER BY v DESC LIMIT %s""",
                ("%" + n.upper() + "%", a.max)).fetchall()
            if not rows: print(f"\n[{n}] nenhum fornecedor com CNPJ de 14 dígitos")
            for cnpj, razao, origem, v in rows:
                print(f"\n[{n}] gravado como {origem}, R$ {v:,.0f} em contratos de TI")
                mostrar(cnpj, razao)
        conn.close()
    if not a.cnpj and not a.nomes:
        ap.print_help()

if __name__ == "__main__":
    main()
