import classifier

import pytest

@pytest.fixture
def fake(monkeypatch):
    def _set(base):
        monkeypatch.setattr(classifier, "_consulta", lambda cnpj: base.get(cnpj))
    return _set

def test_hyperscaler_por_nome():
    r = classifier.classificar("11111111000111", "AMAZON WEB SERVICES BRASIL LTDA")
    assert r["origem"] == "ESTRANGEIRO" and r["hyperscaler"]

def test_cadeia_ate_socio_estrangeiro(fake):
    fake({
      "11111111000111": dict(razao_social="ALFA LTDA", qsa=[dict(identificador_de_socio=1,
          cnpj_cpf_do_socio="22222222000122", nome_socio="BETA HOLDING")]),
      "22222222000122": dict(razao_social="BETA HOLDING", qsa=[dict(identificador_de_socio=3,
          nome_socio="FOREIGN CORP INC")]),
    })
    r = classifier.classificar("11111111000111", "ALFA LTDA")
    assert r["origem"] == "ESTRANGEIRO" and r["ubo"] == "FOREIGN CORP INC"

def test_nacional_e_ciclo(fake):
    fake({
      "11111111000111": dict(razao_social="ALFA", qsa=[dict(identificador_de_socio=1,
          cnpj_cpf_do_socio="22222222000122", nome_socio="B")]),
      "22222222000122": dict(razao_social="B", qsa=[dict(identificador_de_socio=1,
          cnpj_cpf_do_socio="11111111000111", nome_socio="A")]),
    })
    assert classifier.classificar("11111111000111", "ALFA")["origem"] == "NACIONAL"


def test_empresa_no_exterior_com_cnpj_no_brasil(fake):
    fake({
      "11111111000111": dict(razao_social="DELL BRASIL LTDA", qsa=[dict(identificador_de_socio=1,
          cnpj_cpf_do_socio="22222222000122", nome_socio="DELL INTERNATIONAL SERVICES")]),
      "22222222000122": dict(razao_social="DELL INTERNATIONAL SERVICES",
          natureza_juridica="Empresa Domiciliada no Exterior", qsa=[]),
    })
    r = classifier.classificar("11111111000111", "DELL BRASIL LTDA")
    assert r["origem"] == "ESTRANGEIRO" and "Cadeia societária" in r["motivo"]

def test_socio_com_pais_estrangeiro(fake):
    fake({"11111111000111": dict(razao_social="ALFA", qsa=[dict(identificador_de_socio=2, nome_socio="JOHN",
          pais="ESTADOS UNIDOS")])})
    assert classifier.classificar("11111111000111", "ALFA")["origem"] == "ESTRANGEIRO"

def test_socio_pais_brasil_nao_e_estrangeiro(fake):
    fake({"11111111000111": dict(razao_social="ALFA", qsa=[dict(identificador_de_socio=2, nome_socio="MARIA",
          pais="BRASIL")])})
    assert classifier.classificar("11111111000111", "ALFA")["origem"] == "NACIONAL"


def test_socio_pj_estrangeiro_como_a_brasilapi_devolve(fake):
    fake({"72381189000110": dict(razao_social="DELL COMPUTADORES DO BRASIL LTDA",
          natureza_juridica="Sociedade Empresária Limitada", qsa=[
            dict(identificador_de_socio=1, nome_socio="DELL GLOBAL BV", cnpj_cpf_do_socio="11287916",
                 pais="Países Baixos (Holanda)", qualificacao_socio="Sócio Pessoa Jurídica Domiciliado no Exterior"),
            dict(identificador_de_socio=2, nome_socio="DIEGO", cnpj_cpf_do_socio="***326170**", pais=None,
                 qualificacao_socio="Administrador")])})
    r = classifier.classificar("72381189000110", "DELL COMPUTADORES DO BRASIL LTDA")
    assert r["origem"] == "ESTRANGEIRO" and r["ubo"] == "DELL GLOBAL BV"

def test_qualificacao_exterior_basta_mesmo_sem_pais(fake):
    fake({"11111111000111": dict(razao_social="ALFA", qsa=[dict(identificador_de_socio=1, nome_socio="X HOLDING",
          cnpj_cpf_do_socio="12345678", pais=None, qualificacao_socio="Sócio Pessoa Jurídica Domiciliado no Exterior")])})
    assert classifier.classificar("11111111000111", "ALFA")["origem"] == "ESTRANGEIRO"

def test_matriz_de():
    assert classifier.matriz_de("72381189001354") == "72381189000110"
    assert classifier.matriz_de("00000000000191") == "00000000000191"

def test_filial_com_http_500_usa_a_matriz(monkeypatch):
    filial, matriz = "72381189001354", "72381189000110"
    def fake(c):
        if c == filial: raise classifier.ConsultaFalhou("HTTP 500")
        return dict(razao_social="DELL", qsa=[dict(identificador_de_socio=1, nome_socio="DELL GLOBAL BV",
                    pais="Países Baixos (Holanda)", cnpj_cpf_do_socio="11287916")]) if c == matriz else None
    monkeypatch.setattr(classifier, "_consulta", fake)
    assert classifier.classificar(filial, "DELL COMPUTADORES DO BRASIL LTDA")["origem"] == "ESTRANGEIRO"

def test_5xx_persistente_faz_so_2_tentativas(monkeypatch, tmp_path):
    monkeypatch.setattr(classifier, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(classifier, "USAR_CNPJWS", False)
    chamadas = []
    class R:
        status_code = 500
        def json(self): return {}
    monkeypatch.setattr(classifier.requests, "get", lambda *a, **k: chamadas.append(1) or R())
    monkeypatch.setattr(classifier.time, "sleep", lambda s: None)
    classifier._CACHE.clear()
    with pytest.raises(classifier.ConsultaFalhou):
        classifier._consulta("11111111000111")
    assert len(chamadas) == 2
    classifier._CACHE.clear()


def test_cache_em_disco_evita_repetir_consulta(monkeypatch, tmp_path):
    monkeypatch.setattr(classifier, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(classifier.time, "sleep", lambda s: None)
    chamadas = []
    class R:
        status_code = 200
        def json(self): return dict(razao_social="ALFA LTDA", qsa=[])
    monkeypatch.setattr(classifier.requests, "get", lambda *a, **k: chamadas.append(1) or R())
    classifier._CACHE.clear()
    assert classifier._consulta("11111111000111")["razao_social"] == "ALFA LTDA"
    classifier._CACHE.clear()
    assert classifier._consulta("11111111000111")["razao_social"] == "ALFA LTDA"
    assert len(chamadas) == 1
    classifier._CACHE.clear()

def test_falha_de_rede_nao_grava_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(classifier, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(classifier, "USAR_CNPJWS", False)
    monkeypatch.setattr(classifier.time, "sleep", lambda s: None)
    class R:
        status_code = 500
        def json(self): return {}
    monkeypatch.setattr(classifier.requests, "get", lambda *a, **k: R())
    classifier._CACHE.clear()
    with pytest.raises(classifier.ConsultaFalhou):
        classifier._consulta("11111111000111")
    assert list(tmp_path.iterdir()) == []
    classifier._CACHE.clear()


def test_de_cnpjws_pf_brasileira_e_pj_estrangeira():
    j = dict(razao_social="ALFA S.A.", natureza_juridica=dict(id="2054", descricao="Sociedade Anônima Fechada"),
             socios=[
        dict(cpf_cnpj_socio="***257668**", nome="ANA", tipo="Pessoa Física",
             qualificacao_socio=dict(descricao="Administrador "), pais=dict(iso2="BR", nome="Brasil")),
        dict(cpf_cnpj_socio="12345678", nome="DELL INTERNATIONAL", tipo="Pessoa Jurídica",
             qualificacao_socio=dict(descricao="Sócio Pessoa Jurídica Domiciliado no Exterior"),
             pais=dict(iso2="NL", nome="Países Baixos (Holanda)"))])
    d = classifier._de_cnpjws(j)
    assert d["razao_social"] == "ALFA S.A." and d["qsa"][0]["pais"] == "" and d["qsa"][0]["identificador_de_socio"] == 2
    assert d["qsa"][1]["pais"].startswith("Países Baixos") and classifier._socio_exterior(d["qsa"][1])
    assert not classifier._socio_exterior(d["qsa"][0])

def test_brasilapi_falha_usa_cnpjws_e_grava_no_disco(monkeypatch, tmp_path):
    monkeypatch.setattr(classifier, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(classifier.time, "sleep", lambda s: None)
    visitadas = []
    class R:
        def __init__(self, code, body=None): self.status_code, self._b = code, body or {}
        def json(self): return self._b
    def get(url, **k):
        visitadas.append(url)
        if "brasilapi" in url: return R(500)
        return R(200, dict(razao_social="DATAPREV", natureza_juridica=dict(descricao="Empresa Pública"),
                           socios=[dict(cpf_cnpj_socio="***1**", nome="ANA", tipo="Pessoa Física",
                                        pais=dict(iso2="BR", nome="Brasil"))]))
    monkeypatch.setattr(classifier.requests, "get", get)
    classifier._CACHE.clear()
    r = classifier.classificar("42422253000101", "DATAPREV")
    assert r["origem"] == "NACIONAL"
    classifier._CACHE.clear()
    visitadas.clear()
    assert classifier.classificar("42422253000101", "DATAPREV")["origem"] == "NACIONAL"
    assert visitadas == []
    classifier._CACHE.clear()

def test_ambas_apis_falham_continua_indeterminado(monkeypatch, tmp_path):
    monkeypatch.setattr(classifier, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(classifier.time, "sleep", lambda s: None)
    class R:
        status_code = 500
        def json(self): return {}
    monkeypatch.setattr(classifier.requests, "get", lambda *a, **k: R())
    classifier._CACHE.clear()
    r = classifier.classificar("42422253000101", "DATAPREV")
    assert r["origem"] == "INDETERMINADO" and "Falha" in r["motivo"]
    classifier._CACHE.clear()
