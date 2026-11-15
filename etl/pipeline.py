import argparse, hashlib, os, re, sys, unicodedata
from collections import namedtuple
from datetime import date
import pandas as pd
import requests
import db
from classifier import classificar, _consulta, ConsultaFalhou, dv_cnpj
from enrich import categoria, peso_w
import normalize

Res = namedtuple("Res", "lidos gravados excluidos duplicadas nao_cnpj sem_id")
MAX_FALHAS_SEGUIDAS = 40
FRACAO = 100
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def _coletar(fonte, orgao, ini, fim):
    if fonte == "compras":
        from coleta_compras import contratos
        for c in contratos(orgao, ini, fim):
            yield normalize.de_compras(c, orgao)
    elif fonte == "transparencia":
        from collectors.transparencia import contratos
        for c in contratos(orgao, ini.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y")):
            yield normalize.de_transparencia(c, orgao)
    else:
        raise SystemExit("fonte deve ser 'compras' ou 'transparencia'")

def _classificar_com_cache(conn, c):
    r = db.executar(conn, "SELECT origem,hyperscaler,motivo,ubo FROM fornecedor WHERE cnpj=%s", (c["cnpj"],)).fetchone()
    if r and r[0] != "INDETERMINADO":
        return dict(origem=r[0], hyperscaler=bool(r[1]), motivo=r[2], ubo=r[3])
    return classificar(c["cnpj"], c["nome"])

_STOP = {"LTDA", "EIRELI", "EPP", "COMERCIO", "SERVICOS", "BRASIL", "DOS", "DAS", "DE", "DA", "DO", "SA", "CIA"}

def _tokens(nome: str) -> set:
    t = unicodedata.normalize("NFKD", (nome or "").upper()).encode("ascii", "ignore").decode()
    return {w for w in re.sub(r"[^A-Z0-9 ]", " ", t).split() if len(w) >= 3 and w not in _STOP}

def nomes_parecidos(a: str, b: str) -> bool:
    """metade (arredondada p/ cima) das palavras distintivas do menor nome aparece no outro. evita aceitar um cnpj
    reconstruído que pertence a outra empresa."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb: return False
    return len(ta & tb) >= max(1, -(-min(len(ta), len(tb)) // 2))

_dv_cnpj = dv_cnpj

def reconstruir_cnpj(raw: str):
    """identificador de 9 dígitos parece ser o início do cnpj (ex.: claro 404325440 -> 40432544/0001-47).
    usa os 8 primeiros (raiz) + filial 0001 (matriz) + dígitos verificadores. retorna none se não for 9 dígitos."""
    d = re.sub(r"\D", "", raw or "")
    if len(d) != 9: return None
    b = d[:8] + "0001"
    return b + _dv_cnpj(b)

def classificar_identificador(raw: str, nome: str = "", resolver: bool = True) -> dict:
    """fornecedor sem cnpj válido de 14 dígitos. padrões vistos nos dados reais (premissas inferidas, confirmar no sicaf):
      ex... / estrangeiro_...  fornecedor estrangeiro (ex.: gartner inc, elsevier bv, waters corp)
      pf...                     pessoa física (não conta na dependência; fica indeterminado com motivo próprio)
      6 dígitos                 código de ug de órgão público -> nacional
      9 dígitos                 início do cnpj: reconstrói a matriz e só aceita se o nome da receita bater com o do contrato"""
    raw = (raw or "").strip(); up = raw.upper()
    if up.startswith("EX") or up.startswith("ESTRANGEIRO"):
        return dict(origem="ESTRANGEIRO", hyperscaler=False, ubo=nome or raw,
                    motivo="Identificador de fornecedor estrangeiro (prefixo EX/ESTRANGEIRO)")
    if up.startswith("PF"):
        return dict(origem="INDETERMINADO", hyperscaler=False, ubo=None, motivo="Pessoa física (prefixo PF)")
    if raw.isdigit() and len(raw) == 11:
        return dict(origem="INDETERMINADO", hyperscaler=False, ubo=None, motivo="CPF (pessoa física)")
    if raw.isdigit() and len(raw) == 6:
        return dict(origem="NACIONAL", hyperscaler=False, ubo=None, motivo="Órgão público (código UG de 6 dígitos)")
    if raw.isdigit() and len(raw) == 9 and resolver:
        cnpj = reconstruir_cnpj(raw)
        try:
            dados = _consulta(cnpj)
        except ConsultaFalhou as e:
            return dict(origem="INDETERMINADO", hyperscaler=False, ubo=None,
                        motivo=f"Falha ao reconstruir CNPJ de 9 dígitos ({e})")
        if dados and nomes_parecidos(dados.get("razao_social", ""), nome):
            cl = classificar(cnpj, nome)
            cl["motivo"] = f"CNPJ reconstruído {cnpj} (9 dígitos): " + cl["motivo"]
            return cl
        return dict(origem="INDETERMINADO", hyperscaler=False, ubo=None,
                    motivo="Identificador de 9 dígitos sem correspondência de nome com a matriz reconstruída")
    return dict(origem="INDETERMINADO", hyperscaler=False, ubo=None,
                motivo="Identificador não-CNPJ (possível fornecedor estrangeiro)")

def persistir(conn, c: dict, cl: dict):
    db.executar(conn, """INSERT INTO fornecedor(cnpj,razao_social,origem,hyperscaler,motivo,ubo)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (cnpj) DO UPDATE SET origem=EXCLUDED.origem,
        hyperscaler=EXCLUDED.hyperscaler, motivo=EXCLUDED.motivo, ubo=EXCLUDED.ubo
        WHERE fornecedor.origem='INDETERMINADO'""",
        (c["cnpj"], c["nome"], cl["origem"], bool(cl["hyperscaler"]), cl["motivo"], cl["ubo"]))
    db.executar(conn, """INSERT INTO contrato(id,fonte,orgao,ug,fornecedor_cnpj,objeto,valor,data_inicio,data_fim,categoria,peso_w)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET
        categoria=EXCLUDED.categoria, peso_w=EXCLUDED.peso_w, valor=EXCLUDED.valor, data_fim=EXCLUDED.data_fim""",
        (c["id"], c["fonte"], c["orgao"], c.get("ug", ""), c["cnpj"], c["objeto"], float(c["valor"]),
         c["data_inicio"], c.get("data_fim"), categoria(c["objeto"]),
         float(peso_w(c["objeto"], cl["origem"], cl["hyperscaler"]))))

def _amostrar_descartado(conn, c):
    if int(hashlib.md5(c["id"].encode()).hexdigest(), 16) % FRACAO == 0:
        db.executar(conn, """INSERT INTO amostra_descartados(id,orgao,ano,objeto,valor) VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING""", (c["id"], c["orgao"], int((c["data_inicio"] or "0000")[:4] or 0),
                                              c["objeto"], float(c["valor"])))

def rodar_orgao_ano(conn, fonte, orgao, ano, forcar=False):
    """retorna res(lidos, gravados, excluidos, duplicadas, nao_cnpj, sem_id) ou none se já concluído antes."""
    if not forcar and db.executar(conn, "SELECT 1 FROM coleta_log WHERE fonte=%s AND orgao=%s AND ano=%s",
                                  (fonte, orgao, ano)).fetchone():
        return None
    db.executar(conn, "DELETE FROM contrato WHERE fonte=%s AND orgao=%s AND data_inicio>=%s AND data_inicio<=%s",
                (fonte, orgao, f"{ano}-01-01", f"{ano}-12-31"))
    lidos = gravados = excl = dups = nao_cnpj = sem_id = 0
    escolhidos = {}
    for c in _coletar(fonte, orgao, date(ano, 1, 1), date(ano, 12, 31)):
        lidos += 1
        if (c["data_inicio"] or "")[:4] != str(ano):
            continue
        ant = escolhidos.get(c["id"])
        if ant is not None:
            dups += 1
            if (c.get("inclusao") or "") < (ant.get("inclusao") or ""):
                continue
        escolhidos[c["id"]] = c
    for c in escolhidos.values():
        if c.get("excluir"):
            excl += 1; continue
        if categoria(c["objeto"]) == "OUTRO":
            _amostrar_descartado(conn, c); continue
        if not c["data_inicio"]:
            continue
        if len(c["cnpj"]) == 14:
            cl = _classificar_com_cache(conn, c)
        else:
            raw = (c.get("ni") or "").strip()
            if not raw:
                sem_id += 1; continue
            c = dict(c, cnpj=raw[:30])
            cl = classificar_identificador(raw, c.get("nome", ""))
            nao_cnpj += 1
        persistir(conn, c, cl); gravados += 1
        if gravados % 100 == 0: conn.commit()
    db.executar(conn, """INSERT INTO coleta_log(fonte,orgao,ano,lidos,gravados) VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (fonte,orgao,ano) DO UPDATE SET lidos=EXCLUDED.lidos, gravados=EXCLUDED.gravados,
        concluido_em=now()""", (fonte, orgao, ano, lidos, gravados))
    conn.commit()
    return Res(lidos, gravados, excl, dups, nao_cnpj, sem_id)

def _rodar_lista(conn, fonte, orgaos, a0, a1, forcar=False):
    if fonte == "compras":
        import coleta_compras
        print(f"coletor: {coleta_compras.VERSAO}", flush=True)
    for n, o in enumerate(orgaos, 1):
        for ano in range(a0, a1 + 1):
            try:
                r = rodar_orgao_ano(conn, fonte, o, ano, forcar=forcar)
            except (requests.RequestException, KeyboardInterrupt) as e:
                conn.rollback()
                if isinstance(e, KeyboardInterrupt): raise
                print(f"[{n}/{len(orgaos)}] {o}/{ano} FALHOU ({str(e)[:80]}) - rode de novo para retomar", flush=True); continue
            if r is None:
                print(f"[{n}/{len(orgaos)}] {o}/{ano}: já concluído", flush=True); continue
            msg = f"lidos={r[0]} (duplicadas={r[3]}) gravados(TI)={r[1]} [não-CNPJ={r[4]} sem-id={r[5]}] excluídos={r[2]}"
            print(f"[{n}/{len(orgaos)}] {o}/{ano}: " + msg, flush=True)


def reclassificar(conn, todos=False, retomar=False):
    """refaz a classificação dos fornecedores indeterminado (ex.: após falhas temporárias da api).
    todos=true refaz também os nacional (use depois de mudar as regras do classificador/identificadores), começando
    pelos de maior valor contratado. cada fornecedor é gravado na hora; se interromper (ctrl+c), rode de novo com
    retomar=true (--retomar) para continuar de onde parou. depois rode 'recategorizar'."""
    import time
    from datetime import datetime, timezone
    db.executar(conn, "CREATE TABLE IF NOT EXISTS execucao (chave TEXT PRIMARY KEY, valor TEXT)")
    params = ()
    if todos:
        chave = "reclassificar_todos_inicio"
        ant = db.executar(conn, "SELECT valor FROM execucao WHERE chave=%s", (chave,)).fetchone()
        if retomar and ant:
            corte = ant[0]
        else:
            corte = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            db.executar(conn, """INSERT INTO execucao(chave,valor) VALUES (%s,%s)
                ON CONFLICT (chave) DO UPDATE SET valor=EXCLUDED.valor""", (chave, corte))
        conn.commit()
        filtro, params = "WHERE (f.classificado_em IS NULL OR f.classificado_em < %s)", (corte,)
    else:
        filtro = "WHERE f.origem='INDETERMINADO'"
    rows = db.executar(conn, f"""SELECT f.cnpj, f.razao_social, f.origem, COALESCE(SUM(c.valor),0) AS v
        FROM fornecedor f LEFT JOIN contrato c ON c.fornecedor_cnpj=f.cnpj {filtro}
        GROUP BY f.cnpj, f.razao_social, f.origem ORDER BY v DESC, f.cnpj""", params).fetchall()
    rows = sorted(rows, key=lambda r: (len(r[0]) == 14 and r[0].isdigit(), -float(r[3] or 0), r[0]))
    mudou, t0, seguidas, falhou = 0, time.time(), 0, []
    for n, (cnpj, nome, antes, _v) in enumerate(rows, 1):
        cl = classificar(cnpj, nome or "") if (len(cnpj) == 14 and cnpj.isdigit()) else classificar_identificador(cnpj, nome or "")
        if cl["origem"] == "INDETERMINADO" and antes != "INDETERMINADO" and "Falha" in cl["motivo"]:
            print(f"[{n}/{len(rows)}] {cnpj} {nome}: API falhou ({cl['motivo']}); mantido como {antes}", flush=True)
            seguidas += 1; falhou.append((cnpj, nome, float(_v or 0)))
            if seguidas >= MAX_FALHAS_SEGUIDAS:
                print(f"\n{seguidas} falhas seguidas: a BrasilAPI parece fora do ar ou limitando. Parei para não perder tempo.\n"
                      f"O que já foi revisto está salvo. Tente mais tarde: python pipeline.py reclassificar --todos --retomar")
                return n
            continue
        seguidas = 0
        db.executar(conn, "UPDATE fornecedor SET origem=%s, hyperscaler=%s, motivo=%s, ubo=%s, classificado_em=now() WHERE cnpj=%s",
                    (cl["origem"], bool(cl["hyperscaler"]), cl["motivo"], cl["ubo"], cnpj))
        conn.commit()
        if cl["origem"] != antes:
            mudou += 1
            print(f"[{n}/{len(rows)}] {cnpj} {(nome or '')[:40]}: {antes} -> {cl['origem']} ({cl['motivo']})", flush=True)
        elif n % 50 == 0:
            dec = time.time() - t0
            print(f"[{n}/{len(rows)}] ... {dec/60:.1f} min; faltam ~{dec/n*(len(rows)-n)/60:.0f} min", flush=True)
    print(f"{len(rows)} fornecedores revistos; {mudou} mudaram de origem")
    if falhou:
        print(f"\n{len(falhou)} fornecedores SEM RESPOSTA da API (mantiveram a classificação anterior), R$ {sum(f[2] for f in falhou):,.0f} em contratos. Maiores:")
        for c_, n_, v_ in sorted(falhou, key=lambda f: -f[2])[:15]:
            print(f"  {c_}  R$ {v_:,.0f}  {(n_ or '')[:50]}")
    return len(rows)

def recategorizar(conn):
    """recalcula categoria e peso_w de todos os contratos gravados (após mudar palavras-chave ou origem dos
    fornecedores), sem recoletar. contratos que passam a outro ficam na tabela e não entram no idt."""
    rows = db.executar(conn, """SELECT c.id, c.objeto, c.categoria, c.valor, f.origem, f.hyperscaler
                                FROM contrato c JOIN fornecedor f ON f.cnpj=c.fornecedor_cnpj""").fetchall()
    trocas = {}
    for id_, obj, antiga, valor, origem, hyper in rows:
        nova = categoria(obj)
        if nova != antiga:
            t = trocas.setdefault((antiga, nova), [0, 0.0]); t[0] += 1; t[1] += float(valor or 0)
        db.executar(conn, "UPDATE contrato SET categoria=%s, peso_w=%s WHERE id=%s",
                    (nova, float(peso_w(obj, origem, bool(hyper))), id_))
    conn.commit()
    print(f"{len(rows)} contratos recalculados; {sum(t[0] for t in trocas.values())} mudaram de categoria")
    for (a, n), (q, v) in sorted(trocas.items(), key=lambda kv: -kv[1][1]):
        print(f"  {a} -> {n}: {q} contratos, R$ {v:,.0f}")
    return trocas

def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    o = sp.add_parser("orgao"); o.add_argument("fonte"); o.add_argument("codigo")
    o.add_argument("ano_ini", type=int); o.add_argument("ano_fim", type=int)
    o.add_argument("--forcar", action="store_true", help="reprocessa mesmo se já concluído")
    r_ = sp.add_parser("reclassificar"); r_.add_argument("--todos", action="store_true", help="refaz também os NACIONAL")
    r_.add_argument("--retomar", action="store_true", help="com --todos: continua a rodada anterior (pula quem já foi revisto)")
    sp.add_parser("recategorizar")
    v = sp.add_parser("validados"); v.add_argument("ano_ini", type=int); v.add_argument("ano_fim", type=int)
    v.add_argument("--forcar", action="store_true")
    v.add_argument("--so", nargs="*", default=None, help="processa apenas estes códigos de órgão")
    v.add_argument("--excluir", nargs="*", default=[], help="códigos de órgão a pular (ex.: Judiciário)")
    a = ap.parse_args()
    conn = db.connect(); db.init_schema(conn)
    if a.cmd == "reclassificar":
        reclassificar(conn, a.todos, a.retomar)
    elif a.cmd == "recategorizar":
        recategorizar(conn)
    elif a.cmd == "orgao":
        _rodar_lista(conn, a.fonte, [a.codigo], a.ano_ini, a.ano_fim, a.forcar)
    else:
        arq = os.path.join(DATA, "orgaos_validados.csv")
        if not os.path.exists(arq): raise SystemExit("Rode antes: discover_orgaos.py resumo")
        lista = pd.read_csv(arq, dtype=str)
        orgaos = [c for c in lista.codigo_orgao if c not in set(a.excluir) and (a.so is None or c in set(a.so))]
        _rodar_lista(conn, "compras", orgaos, a.ano_ini, a.ano_fim, a.forcar)
    conn.close()

if __name__ == "__main__":
    main()
