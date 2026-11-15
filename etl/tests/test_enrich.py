from enrich import categoria, peso_w

def test_falsos_positivos_corrigidos():
    assert categoria("Capacitação de servidores públicos federais") == "OUTRO"
    assert categoria("Manutenção da rede de esgoto e rede elétrica") == "OUTRO"
    assert categoria("Serviço de hospedagem de participantes do evento") == "OUTRO"

def test_categorias_de_ti():
    assert categoria("AQUISIÇÃO DE SOLUÇÕES EM TIC (SWITCHES, MEMÓRIA E ARMAZENAMENTO)") == "INFRA"
    assert categoria("Contratação de serviços em nuvem (IaaS)") == "NUVEM"
    assert categoria("Plataforma de inteligência artificial generativa") == "IA"
    assert categoria("Licenças de uso de software de gestão") == "TIC"
    assert categoria("Aquisição de servidores rack para o datacenter") in ("INFRA", "NUVEM")

def test_pesos():
    assert peso_w("serviço de nuvem", "NACIONAL", False) == 0.0
    assert peso_w("serviço de nuvem", "ESTRANGEIRO", True) == 1.5
    assert peso_w("solução open source de IA", "ESTRANGEIRO", False) == 0.3
    assert peso_w("licenças de software", "ESTRANGEIRO", False) == 1.0


def test_exclusoes_da_auditoria_2024_2025():
    assert categoria("Vagas em curso de mestrado em inteligência artificial") == "OUTRO"
    assert categoria("Apoio a projeto de pós-graduação em IA via fundação interveniente") == "OUTRO"
    assert categoria("Aquisição de scanner de raio X com recurso de inteligência artificial") != "IA"
    assert categoria("Serviço de PABX em nuvem") == "TIC"
    assert categoria("Telefonia IP em nuvem para o órgão") == "TIC"
    assert categoria("Prestação de serviços estratégicos de TIC, incluindo nuvem, IA e data center") == "TIC"
    assert categoria("Contratação de serviços de computação em nuvem (IaaS)") == "NUVEM"


def test_ajustes_da_segunda_auditoria():
    assert categoria("SERVIÇO TELEFÔNICO FIXO COMUTADO (STFC) ATRAVÉS DE SOLUÇÃO DE PBX VIRTUAL EM NUVEM") == "TIC"
    assert categoria("Solução para desbloqueio e extração avançada de dados de celulares, incluindo nuvem") != "NUVEM"
    assert categoria("Licenças educacionais do software Adobe Creative Cloud por 36 meses") == "TIC"
    for t in ["Aquisição de câmeras digitais com IA", "Smartphone Samsung S24 com inteligência artificial",
              "Dispositivos inteligentes de videoconferência com recursos de inteligência artificial",
              "Manutenção de elevadores com software com inteligência artificial"]:
        assert categoria(t) != "IA", t
    assert categoria("Aquisição de servidor de IA para a pró-reitoria") == "INFRA"
    assert categoria("Aquisição de workstation para IA") == "INFRA"
    assert categoria("Contratação de plataforma de inteligência artificial para triagem de processos") == "IA"
    assert categoria("Serviços de nuvem do provedor Microsoft Azure") == "NUVEM"


def test_falsos_positivos_do_relatorio_de_11_10():
    assert categoria("AQUISIÇÃO DE 8 KITS DE PCR PARA INFLUENZA AVIÁRIA (IA)") != "IA"
    assert categoria("TERMO DE REFERÊNC IA.. NOBREAKS 1500VA COM MONITORAMENTO POR WI-FI") != "IA"
    assert categoria("EXECUÇÃO DAS ATIVIDADES DE APOIO LOGÍSTICO DO PROJETO INTITULADO DIAGNÓSTICO UTILIZANDO INTELIGÊNCIA ARTIFICIAL") != "IA"
    assert categoria("SUBSCRIÇÕES DE LICENÇA DE SOFTWARE – ELASTIC CLOUD ENTERPRISE – ECE") != "NUVEM"
    assert categoria("AQUISIÇÃO DE ASSINATURAS DE PROGRAMAS DE INTELIGÊNCIA ARTIFICIAL - IA - TR DIGITAL") == "IA"
    assert categoria("AQUISIÇÃO DE FERRAMENTA DE INTELIGÊNCIA ARTIFICIAL ESPECIALIZADA EM CONTRATAÇÃO PÚBLICA") == "IA"


def test_fundacao_de_apoio_nao_e_tic():
    assert categoria('EXECUÇÃO DAS ATIVIDADES DE APOIO LOGÍSTICO, ADMINISTRATIVO E GESTÃO FINANCEIRA DO PROJETO INTITULADO "FOMENTAR A TECNOLOGIA"') == "OUTRO"
    assert categoria("Contratação de licenças de software de gestão") == "TIC"


def test_ajustes_da_validacao_rotulada():
    from enrich import categoria
    assert categoria("CURSOS DE INTELIGÊNCIA ARTIFICIAL") == "OUTRO"
    assert categoria("KITS PARA DIAGNÓSTICO DE IA E DNC POR PCR") == "OUTRO"
    assert categoria("AQUISIÇÃO DE INFRAESTRUTURA COMPUTACIONAL HIPERCONVERGENTE - CLOUD PRIVADA") == "INFRA"
    assert categoria("EMISSÃO DE CERFICADO DIGITAL A3 EM NUVEM") != "NUVEM"
    assert categoria("AQUISIÇÃO DE COMPUTADOR") == "TIC"
    assert categoria("SERVIÇO DE COMPUTAÇÃO EM NUVEM") == "NUVEM"


def test_contratos_grandes_conferidos():
    from enrich import categoria, intermediacao_nuvem
    claro = "FORNECIMENTO DE UNIDADES DE SERVIÇOS TÉCNICOS DE INTERMEDIAÇÃO PARA NUVENS PÚBLICAS (USIN'S E USIN'S MP)"
    assert categoria(claro) == "NUVEM" and intermediacao_nuvem(claro)
    pf = 'LICENÇAS DE SOFTWARE, APLICATIVOS E SISTEMAS OPERACIONAIS, DESTINADOS AOS EQUIPAMENTOS, ESTAÇÕES DE TRABALHO E SERVIDORES DE REDE DA POLÍCIA FEDERAL'
    assert categoria(pf) == "TIC"
    o365 = "SUÍTE DE ESCRITÓRIO MICROSOFT OFFICE 365, E1 E E3, E ASSISTENTE DE INTELIGÊNCIA ARTIFICIAL, COPILOT PARA MICROSOFT 365"
    assert categoria(o365) == "NUVEM"
    assert categoria("SUBSCRIÇÕES DO MICROSOFT COPILOT M365 – 12 MESES") == "IA"
    assert categoria("AQUISIÇÃO DE SWITCHES COM LICENÇAS DE SOFTWARE") == "INFRA"
