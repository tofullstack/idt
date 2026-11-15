import pandas as pd

def _ponderado(c: pd.DataFrame, freq: str, modo: str) -> pd.Series:
    if modo == "inicio":
        c = c.assign(periodo=pd.to_datetime(c["data_inicio"]).dt.to_period(freq).dt.to_timestamp())
        return (c["valor"] * c["peso_w"]).groupby(c["periodo"]).sum()
    linhas = []
    fins = pd.to_datetime(c["data_fim"]) if "data_fim" in c else pd.Series(pd.NaT, index=c.index)
    for ini, fim, v, w in zip(pd.to_datetime(c["data_inicio"]), fins, c["valor"], c["peso_w"]):
        if pd.isna(fim) or fim < ini: fim = ini
        ps = pd.period_range(ini.to_period(freq), fim.to_period(freq), freq=freq)
        linhas += [(p.to_timestamp(), v * w / len(ps)) for p in ps]
    return pd.DataFrame(linhas, columns=["periodo", "x"]).groupby("periodo")["x"].sum()

def calcular_idt(contratos: pd.DataFrame, invest: pd.DataFrame, freq: str = "M", modo: str = "inicio") -> pd.DataFrame:
    """contratos: data_inicio, [data_fim], valor, peso_w, categoria | invest: periodo, valor"""
    c = contratos[contratos["categoria"].isin(["NUVEM", "IA"])]
    num = _ponderado(c, freq, modo).rename("numerador") if len(c) else pd.Series(dtype=float, name="numerador")
    i = invest.copy()
    i["periodo"] = pd.to_datetime(i["periodo"]).dt.to_period(freq).dt.to_timestamp()
    den = i.groupby("periodo")["valor"].sum().rename("denominador")
    df = pd.concat([num, den], axis=1).fillna({"numerador": 0}).reset_index(names="periodo")
    df["idt"] = (df["numerador"] / df["denominador"]).where(df["denominador"] > 0) * 100
    return df
