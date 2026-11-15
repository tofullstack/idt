import argparse, pandas as pd
import db
from enrich import peso_w
from idt import calcular_idt

def _f(x): return None if pd.isna(x) else float(x)

def run(modo="inicio", indeterminado="zero"):
    conn = db.connect(); db.init_schema(conn)
    c = pd.read_sql("""SELECT c.data_inicio, c.data_fim, c.valor, c.categoria, c.objeto, f.origem, f.hyperscaler
                       FROM contrato c JOIN fornecedor f ON f.cnpj = c.fornecedor_cnpj""", conn)
    i = pd.read_sql("SELECT periodo, valor FROM investimento_infra", conn)
    c["valor"] = c["valor"].astype(float); i["valor"] = i["valor"].astype(float)
    c["peso_w"] = [peso_w(o, og, bool(h), indeterminado) for o, og, h in zip(c.objeto, c.origem, c.hyperscaler)]
    alvo = c[c.categoria.isin(["NUVEM", "IA"])]
    if len(alvo) and alvo.valor.sum() > 0:
        ind = alvo.loc[alvo.origem == "INDETERMINADO", "valor"].sum() / alvo.valor.sum()
        print(f"NUVEM+IA: {len(alvo)} contratos; {ind:.1%} do valor com fornecedor INDETERMINADO (modo '{indeterminado}')")
    df = calcular_idt(c, i, modo=modo)
    for r in df.itertuples():
        db.executar(conn, """INSERT INTO idt_serie(periodo,numerador,denominador,idt) VALUES (%s,%s,%s,%s)
            ON CONFLICT (periodo) DO UPDATE SET numerador=EXCLUDED.numerador, denominador=EXCLUDED.denominador,
            idt=EXCLUDED.idt, calculado_em=now()""",
            (r.periodo.strftime("%Y-%m-%d"), _f(r.numerador), _f(r.denominador), _f(r.idt)))
    conn.commit(); conn.close(); print(f"{len(df)} períodos gravados (modo={modo})")
    return df

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["inicio", "proporcional"], default="inicio")
    ap.add_argument("--indeterminado", choices=["zero", "estrangeiro"], default="zero")
    a = ap.parse_args(); run(a.modo, a.indeterminado)
