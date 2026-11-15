import pandas as pd
import pytest
import config, db, pipeline, calc_idt, load_invest

def contrato(i, cnpj, objeto, valor, ini, fim, excluir=None):
    return dict(id=f"compras:{i}", fonte="compras", orgao="26246", ug="153163", cnpj=cnpj, nome="X",
                objeto=objeto, valor=valor, data_inicio=ini, data_fim=fim, excluir=excluir)

@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path/'t.db'}")
    conn = db.connect(); db.init_schema(conn)
    yield conn
    conn.close()

def test_pipeline_ponta_a_ponta(banco, monkeypatch, tmp_path):
    dados = [
        contrato(1, "11111111000111", "Serviços de computação em nuvem", 1200.0, "2024-01-15", "2024-12-14"),
        contrato(2, "22222222000122", "Licenças de uso de software", 500.0, "2024-02-01", "2025-02-01"),
        contrato(3, "11111111000111", "Serviços de nuvem excluído", 999.0, "2024-03-01", "2024-12-31", excluir="contrato excluído"),
        contrato(4, "33333333000133", "Compra de gêneros alimentícios", 50.0, "2024-04-01", "2024-12-31"),
        contrato(5, "123", "Serviços de nuvem sem CNPJ válido", 70.0, "2024-05-01", "2024-12-31"),
    ]
    monkeypatch.setattr(pipeline, "_coletar", lambda *a, **k: iter(dados))
    chamadas = []
    def fake_classificar(cnpj, nome):
        chamadas.append(cnpj)
        est = cnpj == "11111111000111"
        return dict(origem="ESTRANGEIRO" if est else "NACIONAL", hyperscaler=est, ubo=None, motivo="teste")
    monkeypatch.setattr(pipeline, "classificar", fake_classificar)

    r = pipeline.rodar_orgao_ano(banco, "compras", "26246", 2024)
    assert (r.lidos, r.gravados, r.excluidos) == (5, 2, 1)
    assert pipeline.rodar_orgao_ano(banco, "compras", "26246", 2024) is None
    n = len(chamadas); pipeline.rodar_orgao_ano(banco, "compras", "26246", 2024, forcar=True)
    assert len(chamadas) == n

    cats = dict(banco.execute("SELECT id, categoria FROM contrato").fetchall())
    assert cats == {"compras:1": "NUVEM", "compras:2": "TIC"}
    assert banco.execute("SELECT COUNT(*) FROM contrato").fetchone()[0] == 2

    inv = tmp_path / "inv.csv"
    pd.DataFrame(dict(periodo=["2024-01-01", "2024-06-01"], valor=[1000, 1000], fonte=["T", "T"])).to_csv(inv, index=False)
    load_invest.carregar(str(inv))
    df = calc_idt.run("proporcional")
    jan = df[df.periodo == "2024-01-01"].iloc[0]
    assert round(jan.numerador, 2) == 150.0 and round(jan.idt, 2) == 15.0
    assert banco.execute("SELECT COUNT(*) FROM idt_serie").fetchone()[0] == len(df)


def test_dv_cnpj_e_reconstrucao():
    assert pipeline.reconstruir_cnpj("000000000") == "00000000000191"
    assert pipeline.reconstruir_cnpj("12345") is None

def test_nomes_parecidos():
    assert pipeline.nomes_parecidos("CLARO S.A.", "CLARO SA")
    assert pipeline.nomes_parecidos("EMBRATEL TVSAT TELECOMUNICACOES SA", "EMBRATEL TELECOMUNICACOES S.A.")
    assert not pipeline.nomes_parecidos("PADARIA PAO QUENTE LTDA", "CLARO S.A.")
    assert not pipeline.nomes_parecidos("", "CLARO S.A.")

@pytest.mark.parametrize("raw,origem", [
    ("EX123456", "ESTRANGEIRO"), ("ESTRANGEIRO_GARTNER", "ESTRANGEIRO"),
    ("PF000123", "INDETERMINADO"), ("12345678901", "INDETERMINADO"),
    ("153163", "NACIONAL"), ("ABC", "INDETERMINADO")])
def test_classificar_identificador_padroes(raw, origem):
    assert pipeline.classificar_identificador(raw, "FORNECEDOR X")["origem"] == origem

def test_identificador_9_digitos_so_aceita_se_o_nome_bater(monkeypatch):
    cnpj = pipeline.reconstruir_cnpj("404325440")
    monkeypatch.setattr(pipeline, "_consulta", lambda c: dict(razao_social="CLARO S.A.") if c == cnpj else None)
    monkeypatch.setattr(pipeline, "classificar", lambda c, n: dict(origem="ESTRANGEIRO", hyperscaler=False, ubo="AMX", motivo="teste"))
    ok = pipeline.classificar_identificador("404325440", "CLARO SA")
    assert ok["origem"] == "ESTRANGEIRO" and cnpj in ok["motivo"]
    outro = pipeline.classificar_identificador("404325440", "PADARIA PAO QUENTE LTDA")
    assert outro["origem"] == "INDETERMINADO" and "sem correspondência" in outro["motivo"]

def test_identificador_9_digitos_falha_de_rede_nao_vira_nacional(monkeypatch):
    def boom(c): raise pipeline.ConsultaFalhou("HTTP 429")
    monkeypatch.setattr(pipeline, "_consulta", boom)
    r = pipeline.classificar_identificador("404325440", "CLARO SA")
    assert r["origem"] == "INDETERMINADO" and "Falha" in r["motivo"]


def _semear(conn):
    for cnpj, nome, origem in [("11111111000111", "ALFA", "NACIONAL"), ("22222222000122", "BETA", "NACIONAL")]:
        db.executar(conn, "INSERT INTO fornecedor(cnpj,razao_social,origem,hyperscaler,motivo,classificado_em) VALUES (%s,%s,%s,0,'t','2000-01-01 00:00:00')",
                    (cnpj, nome, origem))
    linhas = [("c1", "11111111000111", "Vagas em curso de mestrado em inteligência artificial", 100.0, "IA", 1.5),
              ("c2", "22222222000122", "Contratação de serviços de computação em nuvem", 200.0, "NUVEM", 0.0)]
    for id_, cnpj, obj, v, cat, w in linhas:
        db.executar(conn, """INSERT INTO contrato(id,fonte,orgao,ug,fornecedor_cnpj,objeto,valor,data_inicio,categoria,peso_w)
                             VALUES (%s,'compras','1','1',%s,%s,%s,'2024-01-01',%s,%s)""", (id_, cnpj, obj, v, cat, w))
    conn.commit()

def test_recategorizar_aplica_novas_regras_sem_recoletar(banco):
    _semear(banco)
    trocas = pipeline.recategorizar(banco)
    assert trocas == {("IA", "OUTRO"): [1, 100.0]}
    assert dict(banco.execute("SELECT id, categoria FROM contrato").fetchall()) == {"c1": "OUTRO", "c2": "NUVEM"}

def test_reclassificar_todos_pega_multinacional_marcada_nacional(banco, monkeypatch):
    _semear(banco)
    monkeypatch.setattr(pipeline, "classificar", lambda c, n: dict(
        origem="ESTRANGEIRO" if c == "22222222000122" else "NACIONAL", hyperscaler=False, ubo="X", motivo="teste"))
    pipeline.reclassificar(banco)
    assert banco.execute("SELECT origem FROM fornecedor WHERE cnpj='22222222000122'").fetchone()[0] == "NACIONAL"
    pipeline.reclassificar(banco, todos=True)
    assert banco.execute("SELECT origem FROM fornecedor WHERE cnpj='22222222000122'").fetchone()[0] == "ESTRANGEIRO"

def test_reclassificar_falha_de_rede_nao_rebaixa_quem_ja_estava_classificado(banco, monkeypatch):
    _semear(banco)
    monkeypatch.setattr(pipeline, "classificar", lambda c, n: dict(
        origem="INDETERMINADO", hyperscaler=False, ubo=None, motivo="Falha na consulta (HTTP 429)"))
    pipeline.reclassificar(banco, todos=True)
    assert banco.execute("SELECT COUNT(*) FROM fornecedor WHERE origem='NACIONAL'").fetchone()[0] == 2


def test_reclassificar_todos_pode_ser_retomado(banco, monkeypatch):
    _semear(banco)
    vistos = []
    def fake(c, n):
        vistos.append(c)
        return dict(origem="NACIONAL", hyperscaler=False, ubo=None, motivo="teste")
    monkeypatch.setattr(pipeline, "classificar", fake)
    pipeline.reclassificar(banco, todos=True)
    assert sorted(vistos) == ["11111111000111", "22222222000122"]
    vistos.clear()
    pipeline.reclassificar(banco, todos=True, retomar=True)
    assert vistos == []
    banco.execute("UPDATE fornecedor SET classificado_em='2000-01-01 00:00:00' WHERE cnpj='22222222000122'"); banco.commit()
    pipeline.reclassificar(banco, todos=True, retomar=True)
    assert vistos == ["22222222000122"]
    vistos.clear()
    banco.execute("UPDATE fornecedor SET classificado_em='2000-01-01 00:00:00'"); banco.commit()
    pipeline.reclassificar(banco, todos=True)
    assert len(vistos) == 2


def test_reclassificar_para_quando_a_api_cai(banco, monkeypatch):
    _semear(banco)
    monkeypatch.setattr(pipeline, "MAX_FALHAS_SEGUIDAS", 2)
    vistos = []
    def fake(c, n):
        vistos.append(c)
        return dict(origem="INDETERMINADO", hyperscaler=False, ubo=None, motivo="Falha na consulta (HTTP 500)")
    monkeypatch.setattr(pipeline, "classificar", fake)
    for i in range(3):
        db.executar(banco, "INSERT INTO fornecedor(cnpj,razao_social,origem,hyperscaler,motivo,classificado_em) VALUES (%s,%s,'NACIONAL',0,'t','2000-01-01 00:00:00')",
                    (f"3333333300013{i}", f"F{i}"))
    banco.commit()
    n = pipeline.reclassificar(banco, todos=True)
    assert len(vistos) == 2 and n == 2
    assert banco.execute("SELECT COUNT(*) FROM fornecedor WHERE origem='NACIONAL'").fetchone()[0] == 5


def test_reclassificar_resolve_identificadores_antes_dos_cnpjs_mesmo_com_api_fora(banco, monkeypatch):
    _semear(banco)
    db.executar(banco, "INSERT INTO fornecedor(cnpj,razao_social,origem,hyperscaler,motivo,classificado_em) VALUES ('EX4130003','HARVARD','INDETERMINADO',0,'velho','2000-01-01 00:00:00')")
    banco.commit()
    monkeypatch.setattr(pipeline, "MAX_FALHAS_SEGUIDAS", 1)
    monkeypatch.setattr(pipeline, "classificar", lambda c, n: dict(
        origem="INDETERMINADO", hyperscaler=False, ubo=None, motivo="Falha na consulta (HTTP 500)"))
    pipeline.reclassificar(banco, todos=True)
    assert banco.execute("SELECT origem FROM fornecedor WHERE cnpj='EX4130003'").fetchone()[0] == "ESTRANGEIRO"
