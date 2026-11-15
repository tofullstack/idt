import calendar, sys
from collections import Counter, defaultdict
from datetime import date, timedelta
import coleta_compras as cc
import normalize

def meses(ano):
    for m in range(1, 13):
        yield m, date(ano, m, 1), date(ano, m, calendar.monthrange(ano, m)[1])

def total(orgao, a, b):
    p = cc._get(cc._params(orgao, a, b, 1, 10))
    return int(p.get("totalRegistros") or 0) if isinstance(p, dict) else 0

def veredito(total_ano, soma_meses, ids_repetidos, fora):
    msgs = []
    if soma_meses == total_ano and not ids_repetidos and not fora:
        return ["CONSISTENTE: a soma dos meses bate com o ano, sem ids repetidos nem linhas fora da janela."]
    if soma_meses > total_ano:
        msgs.append(f"SOBREPOSIÇÃO: os meses somam {soma_meses - total_ano} a mais que o ano (a API inclui também o dia SEGUINTE ao fim da janela).")
    if soma_meses < total_ano:
        msgs.append(f"BURACO: os meses somam {total_ano - soma_meses} a menos que o ano (linhas que só aparecem na janela grande).")
    if ids_repetidos: msgs.append(f"{ids_repetidos} ids aparecem em mais de um mês.")
    if fora: msgs.append(f"{fora} linhas têm data fora da janela pedida (vazamento de fronteira).")
    return msgs

def rodar(orgao, ano, dias=False):
    total_ano = sum(total(orgao, a, b) for a, b in cc.split_janelas(date(ano, 1, 1), date(ano, 12, 31)))
    print(f"total do ano (como o pipeline): {total_ano}\n")
    print(f"{'mês':>4} {'total_api':>9} {'linhas':>7} {'fora_janela':>11} {'hora!=0':>8} {'ids_distintos':>13}")
    onde, soma, fora_t, offsets = defaultdict(set), 0, 0, Counter()
    for m, a, b in meses(ano):
        t = total(orgao, a, b); soma += t
        rows = list(cc._paginar(orgao, a, b, 500))
        fora = sum(1 for r in rows if not (a.isoformat() <= str(r.get("dataVigenciaInicial"))[:10] <= b.isoformat()))
        hora = sum(1 for r in rows if str(r.get("dataVigenciaInicial"))[11:19] not in ("", "00:00:00"))
        ids = {normalize.de_compras(r, orgao)["id"] for r in rows}
        for i in ids: onde[i].add(m)
        fora_t += fora
        for r in rows:
            dd = str(r.get('dataVigenciaInicial'))[:10]
            if not (a.isoformat() <= dd <= b.isoformat()):
                offsets[(date.fromisoformat(dd) - a).days if dd < b.isoformat() else (date.fromisoformat(dd) - b).days + 1000] += 1
        print(f"{m:>4} {t:>9} {len(rows):>7} {fora:>11} {hora:>8} {len(ids):>13}")
    repetidos = sum(1 for v in onde.values() if len(v) > 1)
    print(f"\nsoma dos meses: {soma} | ids distintos (todos os meses): {len(onde)} | repetidos entre meses: {repetidos}")
    print("deslocamento (dias, relativo ao início da janela) das linhas fora da janela:", dict(offsets))
    if dias:
        sd = sum(total(orgao, d, d) for d in (date(ano, 1, 1) + timedelta(days=i) for i in range(366 if calendar.isleap(ano) else 365)))
        print(f"soma dos DIAS: {sd}")
    print("\n" + "\n".join(veredito(total_ano, soma, repetidos, fora_t)))

if __name__ == "__main__":
    rodar(sys.argv[1], int(sys.argv[2]), "--dias" in sys.argv)
