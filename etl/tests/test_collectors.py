from datetime import date
from collectors.compras import split_janelas
import normalize

def test_janelas_max_365_dias():
    js = list(split_janelas(date(2020, 1, 1), date(2025, 12, 31)))
    assert js[0][0] == date(2020, 1, 1) and js[-1][1] == date(2025, 12, 31)
    assert all((b - a).days + 1 <= 365 for a, b in js)
    for (a1, b1), (a2, b2) in zip(js, js[1:]):
        assert (a2 - b1).days == 1

def test_normalize_compras_tolerante():
    n = normalize.de_compras({"id": 7, "niFornecedor": "12.345.678/0001-90",
        "valorGlobal": "1.234,56", "dataVigenciaInicial": "2024-03-05T00:00:00",
        "objeto": "Serviço de nuvem"}, "26000")
    assert n["cnpj"] == "12345678000190" and n["valor"] == 1234.56
    assert n["data_inicio"] == "2024-03-05" and n["id"] == "compras:7"

def test_normalize_data_br():
    assert normalize._data("05/03/2024") == "2024-03-05"

def test_auditar_acusa_campos_ausentes():
    n, problemas, cand = normalize.auditar_compras({"id": 1, "objeto": "x", "campoValorQualquer": 10}, "26246")
    assert any("cnpj" in p for p in problemas) and any("valor" in p for p in problemas)
    assert "campoValorQualquer" in cand

def test_exclusoes_e_id_composto():
    base = {"codigoUnidadeGestora": "153163", "codigoTipo": "50", "numeroContrato": "00258/2023",
            "valorGlobal": 10.0, "dataVigenciaInicial": "2024-01-02T00:00:00", "dataVigenciaFinal": "2025-01-02T00:00:00"}
    ok = normalize.de_compras(base, "26246")
    assert ok["id"] == "compras:26246-153163-50-00258/2023" and ok["excluir"] is None and ok["data_fim"] == "2025-01-02"
    assert normalize.de_compras({**base, "receitaDespesa": "R"}, "26246")["excluir"]
    assert normalize.de_compras({**base, "contratoExcluido": True}, "26246")["excluir"]
    assert normalize.de_compras({**base, "dataHoraExclusao": "2024-02-01T00:00:00"}, "26246")["excluir"]
