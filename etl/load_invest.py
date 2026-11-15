import sys, pandas as pd
import db

def carregar(caminho):
    df = pd.read_csv(caminho, dtype={"fonte": str})
    if not {"periodo", "valor", "fonte"}.issubset(df.columns):
        raise SystemExit("CSV precisa das colunas periodo, valor, fonte")
    df["periodo"] = pd.to_datetime(df["periodo"]).dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-%d")
    conn = db.connect(); db.init_schema(conn)
    for r in df.itertuples():
        db.executar(conn, """INSERT INTO investimento_infra(periodo,valor,fonte) VALUES (%s,%s,%s)
            ON CONFLICT (periodo,fonte) DO UPDATE SET valor=EXCLUDED.valor""", (r.periodo, float(r.valor), r.fonte))
    conn.commit(); conn.close(); print(f"{len(df)} linhas carregadas")

if __name__ == "__main__":
    carregar(sys.argv[1])
