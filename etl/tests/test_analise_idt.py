import numpy as np, pandas as pd
import analise


def _base():
    c = pd.DataFrame({
        "categoria": ["NUVEM", "NUVEM", "TIC", "INFRA", "TIC", "OUTRO"],
        "valor":     [100.0,   200.0,   300.0, 400.0,   500.0, 999.0],
        "mes":       ["2024-01", "2024-01", "2024-01", "2024-01", "2024-02", "2024-01"],
        "A":         [True,  False, False, False, False, False],
        "B":         [True,  True,  False, False, False, False],
        "C":         [False, False, True,  False, False, False],
    })
    return c


def test_idt_agregado_e_criterio_unico():
    t = analise.idt_serie(_base(), mensal=False).iloc[0]
    assert t.valor_tic == 1500.0
    assert t.valor_dep == 600.0
    assert abs(t.idt - 40.0) < 1e-9


def test_idt_mensal_tem_24_meses_e_bate_com_agregado():
    m = analise.idt_serie(_base())
    assert len(m) == 24
    assert abs(m.valor_dep.sum() / m.valor_tic.sum() * 100 - 40.0) < 1e-9
    assert abs(m.loc[m.mes == "2024-01", "idt"].iloc[0] - 100 * 600 / 1000) < 1e-9
    assert m.loc[m.mes == "2024-02", "idt"].iloc[0] == 0.0
    assert np.isnan(m.loc[m.mes == "2024-03", "idt"].iloc[0])


def test_cenarios_w_sensibilidade():
    t = analise.idt_serie(_base(), mensal=False).iloc[0]
    assert abs(t.idt_W1 - 100 * 650 / 1500) < 1e-9
    assert abs(t.idt_W2 - 100 * 450 / 1500) < 1e-9


def test_com_e_sem_estatais():
    c = _base(); est = pd.Series([False, True, False, False, False, False], index=c.index)
    m, b = analise.idt_tabelas(c, est)
    com, sem = b.set_index("versao").loc["com estatais"], b.set_index("versao").loc["sem estatais"]
    assert abs(com.idt - 40.0) < 1e-9
    assert abs(sem.idt - 100 * 400 / 1300) < 1e-9
    assert {"idt_com_estatais", "idt_sem_estatais"} <= set(m.columns)
