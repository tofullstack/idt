import db, pandas as pd, enrich as E
pd.set_option("display.max_colwidth", None); pd.set_option("display.width", 250)
c = db.connect()
d = pd.read_sql("""SELECT valor, categoria, objeto FROM contrato
                   WHERE substr(fornecedor_cnpj,1,8) = '33683111' AND categoria IN ('NUVEM','IA','TIC','INFRA')
                   ORDER BY valor DESC""", c)
d["marca_hyperscaler"] = d.objeto.map(E.marca_hyperscaler)
d["broker"] = d.objeto.map(E.intermediacao_nuvem)
d["nuvem_no_texto"] = d.objeto.str.lower().str.contains(r"nuvem|cloud|multicloud", regex=True)
print(f"Serpro: {len(d)} contratos, R$ {d.valor.sum():,.0f}\n")
print(d.groupby("categoria").agg(contratos=("valor", "size"), valor=("valor", "sum"),
      marca=("marca_hyperscaler", "sum"), broker=("broker", "sum"), cita_nuvem=("nuvem_no_texto", "sum")).to_string())
x = d[(d.marca_hyperscaler | d.broker | d.nuvem_no_texto)].head(15)
print("\nMaiores contratos que citam nuvem/hyperscaler:")
for _, r in x.iterrows():
    print(f"\n[{r.categoria}] R$ {r.valor:,.0f} | marca={r.marca_hyperscaler} broker={r.broker}\n{r.objeto[:400]}")
