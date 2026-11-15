import pandas as pd
import db

pd.set_option("display.width", 200); pd.set_option("display.max_colwidth", 90)
conn = db.connect(); db.init_schema(conn)
q = lambda s: pd.read_sql(s, conn)

print("== COLETA (órgão x ano concluídos) ==")
print(q("""SELECT l.orgao, l.ano, l.lidos, l.gravados AS linhas_ti,
           (SELECT COUNT(*) FROM contrato c WHERE c.orgao=l.orgao AND substr(CAST(c.data_inicio AS TEXT),1,4)=CAST(l.ano AS TEXT)) AS contratos_distintos
           FROM coleta_log l ORDER BY l.orgao, l.ano""").to_string(index=False))
print("(linhas_ti > contratos_distintos => várias linhas da API caíram na mesma chave; rode diag_duplicados.py)")

print("\n== CONTRATOS POR CATEGORIA x ORIGEM DO FORNECEDOR ==")
print(q("""SELECT c.categoria, f.origem, COUNT(*) AS contratos, ROUND(SUM(c.valor),2) AS valor_total
           FROM contrato c JOIN fornecedor f ON f.cnpj=c.fornecedor_cnpj
           GROUP BY c.categoria, f.origem ORDER BY c.categoria, f.origem""").to_string(index=False))

print("\n== FORNECEDORES POR ORIGEM ==")
print(q("SELECT origem, COUNT(*) AS fornecedores, SUM(hyperscaler) AS hyperscalers FROM fornecedor GROUP BY origem").to_string(index=False))

print("\n== ESTRANGEIROS (maior valor) ==")
print(q("""SELECT f.razao_social, f.ubo, f.motivo, ROUND(SUM(c.valor),2) AS valor
           FROM contrato c JOIN fornecedor f ON f.cnpj=c.fornecedor_cnpj WHERE f.origem='ESTRANGEIRO'
           GROUP BY f.cnpj ORDER BY valor DESC LIMIT 10""").to_string(index=False))

print("\n== INDETERMINADOS (por que não classificou?) ==")
print(q("""SELECT f.motivo, COUNT(DISTINCT f.cnpj) AS fornecedores, COUNT(c.id) AS contratos, ROUND(COALESCE(SUM(c.valor),0),2) AS valor
           FROM fornecedor f LEFT JOIN contrato c ON c.fornecedor_cnpj=f.cnpj
           WHERE f.origem='INDETERMINADO' GROUP BY f.motivo ORDER BY valor DESC""").to_string(index=False))

print("\n== AMOSTRA ALEATÓRIA PARA CONFERIR A CLASSIFICAÇÃO (6 por categoria) ==")
for cat in ("NUVEM", "IA", "INFRA", "TIC"):
    a = q(f"SELECT categoria, valor, objeto FROM contrato WHERE categoria='{cat}' ORDER BY RANDOM() LIMIT 6")
    if len(a): print(a.to_string(index=False)); print()

print("\n== VALOR EM FORNECEDOR INDETERMINADO (por categoria) ==")
print(q("""SELECT c.categoria, ROUND(100.0*SUM(CASE WHEN f.origem='INDETERMINADO' THEN c.valor ELSE 0 END)/SUM(c.valor),1) AS pct_valor_indeterminado
           FROM contrato c JOIN fornecedor f ON f.cnpj=c.fornecedor_cnpj GROUP BY c.categoria""").to_string(index=False))

print("\n== CONTRATOS CUJO OBJETO CITA MARCA HYPERSCALER (revendedores?) ==")
from enrich import marca_hyperscaler
m = q("SELECT c.objeto, c.valor, f.origem, f.razao_social FROM contrato c JOIN fornecedor f ON f.cnpj=c.fornecedor_cnpj")
m = m[m.objeto.apply(marca_hyperscaler)]
print(m.groupby("origem").agg(contratos=("valor", "count"), valor=("valor", "sum")).to_string() if len(m) else "nenhum")

print("\n== AMOSTRA DE DESCARTADOS (1%) ==")
print(q("SELECT COUNT(*) AS n FROM amostra_descartados").to_string(index=False))
print("\n== TOP 20 CONTRATOS NUVEM/IA POR VALOR (confira se são mesmo nuvem/IA) ==")
print(q("""SELECT c.categoria, ROUND(c.valor,0) AS valor, f.origem, substr(f.razao_social,1,30) AS fornecedor, substr(c.objeto,1,110) AS objeto
           FROM contrato c JOIN fornecedor f ON f.cnpj=c.fornecedor_cnpj WHERE c.categoria IN ('NUVEM','IA')
           ORDER BY c.valor DESC LIMIT 20""").to_string(index=False))

print("\n== EXEMPLOS DE FORNECEDORES SEM CNPJ (o que são esses identificadores?) ==")
print(q("""SELECT cnpj AS identificador, substr(razao_social,1,40) AS nome, motivo FROM fornecedor
           WHERE origem='INDETERMINADO' AND motivo LIKE 'Identificador%' ORDER BY RANDOM() LIMIT 12""").to_string(index=False))

print("\n== FORNECEDORES COM NOME DE MULTINACIONAL CONHECIDA (a busca no QSA pegou?) ==")
nomes = ["DELL", "LENOVO", "CISCO", "HEWLETT", "XEROX", "KONICA", "SAP ", "SIEMENS", "HUAWEI", "RED HAT", "VMWARE",
         "ADOBE", "SAMSUNG", "CANON", "EPSON", "RICOH", "ACCENTURE", "SYMANTEC", "KASPERSKY", "FORTINET", "PALO ALTO", "3M "]
cond = " OR ".join(f"UPPER(f.razao_social) LIKE '%{n}%'" for n in nomes)
print(q(f"""SELECT substr(f.razao_social,1,45) AS fornecedor, f.origem, substr(f.motivo,1,50) AS motivo, COUNT(c.id) AS contratos
            FROM fornecedor f LEFT JOIN contrato c ON c.fornecedor_cnpj=f.cnpj WHERE {cond}
            GROUP BY f.cnpj ORDER BY contratos DESC LIMIT 25""").to_string(index=False))
conn.close()
