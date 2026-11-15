import pandas as pd
from idt import calcular_idt

def test_idt_basico():
    c = pd.DataFrame(dict(data_inicio=["2024-01-10", "2024-01-20"], valor=[1000, 500],
                          peso_w=[1.5, 0.0], categoria=["NUVEM", "NUVEM"]))
    i = pd.DataFrame(dict(periodo=["2024-01-01"], valor=[3000]))
    r = calcular_idt(c, i)
    assert round(r.loc[0, "idt"], 2) == 50.0

def test_idt_proporcional_dilui_pelos_meses():
    c = pd.DataFrame(dict(data_inicio=["2024-01-15"], data_fim=["2024-12-14"], valor=[1200.0],
                          peso_w=[1.0], categoria=["NUVEM"]))
    i = pd.DataFrame(dict(periodo=["2024-01-01", "2024-07-01"], valor=[1000.0, 1000.0]))
    r = calcular_idt(c, i, modo="proporcional").set_index("periodo")
    assert round(r.loc["2024-01-01", "idt"], 2) == 10.0 and round(r.loc["2024-07-01", "idt"], 2) == 10.0
