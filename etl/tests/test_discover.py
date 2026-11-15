import os
from discover_orgaos import parse_uasg_csv, agregar_orgaos

AMOSTRA = os.path.join(os.path.dirname(__file__), "..", "data", "uasg_pagina1.csv")

def test_rodape_removido_e_paginas_lidas():
    df, total = parse_uasg_csv(open(AMOSTRA, encoding="utf-8").read())
    assert total == 45
    assert len(df) == 500
    assert not df.codigo_uasg.str.contains("total", na=False).any()
    assert df.codigo_uasg.str.len().eq(6).all()

def test_escopo_federal_separa_municipais():
    df, _ = parse_uasg_csv(open(AMOSTRA, encoding="utf-8").read())
    ag = agregar_orgaos(df).set_index("codigo_orgao")
    assert ag.loc["3000", "escopo"] == "FEDERAL_PROVAVEL"
    assert ag.loc["85213", "escopo"] == "NAO_FEDERAL"
    assert ag.loc["95561", "escopo"] == "NAO_FEDERAL"

import pandas as pd
import discover_orgaos as d

def test_consolidar_pivota_e_filtra_zeros():
    p = pd.DataFrame([
        dict(codigo_orgao="1", ano="2023", http="200", n_registros="10", total="50", nome_orgao="UFSC"),
        dict(codigo_orgao="1", ano="2024", http="200", n_registros="10", total="30", nome_orgao="UFSC"),
        dict(codigo_orgao="2", ano="2023", http="200", n_registros="0", total="0", nome_orgao=""),
        dict(codigo_orgao="3", ano="2023", http="429", n_registros="", total="", nome_orgao=""),
    ])
    v = d.consolidar(p)
    assert list(v.codigo_orgao) == ["1"] and int(v.total.iloc[0]) == 80
    assert v.nome_orgao.iloc[0] == "UFSC" and int(v.c2023.iloc[0]) == 50

def test_sondar_retry_em_429(monkeypatch):
    class R:
        def __init__(s, c, j=None): s.status_code, s._j, s.text = c, j, ""
        def json(s): return s._j
    respostas = [R(429), R(200, {"resultado": [{"codigoOrgao": "9", "nomeOrgao": "X"}], "totalRegistros": 7})]
    monkeypatch.setattr(d.requests, "get", lambda *a, **k: respostas.pop(0))
    monkeypatch.setattr(d.time, "sleep", lambda *_: None)
    r = d.sondar("9", 2024)
    assert r["http"] == 200 and r["total"] == 7 and r["nome_orgao"] == "X"

def test_migracao_de_csv_antigo(tmp_path):
    f = tmp_path / "p.csv"
    pd.DataFrame([dict(codigo_orgao="3000", ano="2024", http="200", total="0")]).to_csv(f, index=False)
    d._migrar_probe(str(f))
    assert list(pd.read_csv(f, dtype=str).columns) == d.COLS
