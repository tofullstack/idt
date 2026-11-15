import db, pandas as pd
pd.set_option("display.max_colwidth", None); pd.set_option("display.width", 250)
c = db.connect()
q = """SELECT valor, categoria, objeto FROM contrato
       WHERE valor > 5000000 AND (objeto LIKE '%INTERMEDIA%NUVE%' OR objeto LIKE '%SISTEMAS OPERACIONAIS%' OR objeto LIKE '%OFFICE 365%')
       ORDER BY valor DESC LIMIT 12"""
for _, r in pd.read_sql(q, c).iterrows():
    print(f"\n[{r.categoria}] R$ {r.valor:,.0f}\n{r.objeto}\n" + "-" * 80)
