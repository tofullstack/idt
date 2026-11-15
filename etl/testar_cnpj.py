import sys, time, requests
import db
conn = db.connect(); db.init_schema(conn)
cnpjs = sys.argv[1:] or [r[0] for r in db.executar(conn, "SELECT cnpj FROM fornecedor WHERE origem='INDETERMINADO'").fetchall()]
for c in cnpjs:
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{c}", timeout=20, headers={"User-Agent": "idt-tcc/0.1"})
        print(c, r.status_code, r.text[:160].replace("\n", " "))
    except requests.RequestException as e:
        print(c, "ERRO", type(e).__name__, str(e)[:100])
    time.sleep(1)
