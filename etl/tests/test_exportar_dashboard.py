import json, os, numpy as np, pandas as pd
import analise, exportar_dashboard as ED


def contratos_sinteticos(seed=0):
    """base sintética só para teste e desenvolvimento do painel (nunca dados reais)."""
    rng = np.random.default_rng(seed)
    meses = pd.period_range(*analise.JANELA, freq="M").astype(str)
    linhas = []
    for mes in meses:
        for i in range(30):
            cat = rng.choice(["NUVEM", "IA", "INFRA", "TIC", "OUTRO"], p=[.08, .02, .15, .65, .10])
            a = rng.random() < .03; b = a or rng.random() < .10; cc = (not b) and rng.random() < .15
            linhas.append(dict(categoria=cat, valor=float(rng.lognormal(11, 1.6)), mes=mes, A=a, B=b, C=cc, origem="ESTRANGEIRO" if b else "NACIONAL",
                               razao_social=f"FORNECEDOR {rng.integers(1, 40)}", fornecedor_cnpj=f"{rng.integers(10**7, 10**8 - 1)}0001"))
    return pd.DataFrame(linhas)


def test_exporta_json_com_e_sem_estatais(tmp_path):
    c = contratos_sinteticos()
    est = pd.Series(False, index=c.index); est.iloc[:5] = True
    d = ED.montar_dados(c, est, sintetico=True)
    assert d["meta"]["sintetico"] is True and d["meta"]["estatais"]["contratos"] >= 0
    assert set(d["versoes"]) == {"com_estatais", "sem_estatais"}
    for v in d["versoes"].values():
        assert len(v["idt_mensal"]) == 24 and len(v["serie_mensal"]) == 24
        assert {"idt", "idt_W1", "idt_W2", "valor_tic", "valor_dep"} <= set(v["idt_bienio"])
        assert 0 <= v["idt_bienio"]["idt"] <= 100
        assert v["concentracao"]["hhi"] > 0
    assert d["versoes"]["sem_estatais"]["idt_bienio"]["contratos"] <= d["versoes"]["com_estatais"]["idt_bienio"]["contratos"]
    caminho = ED.gravar(d, str(tmp_path))
    json.load(open(caminho, encoding="utf-8"))
    assert "NaN" not in open(caminho, encoding="utf-8").read()
