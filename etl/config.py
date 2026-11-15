import os
from dotenv import load_dotenv
load_dotenv()

_PADRAO = "sqlite:///" + os.path.join(os.path.expanduser("~"), "idt_data", "idt.db")
DATABASE_URL = os.getenv("DATABASE_URL", _PADRAO)
TRANSPARENCIA_API_KEY = os.getenv("TRANSPARENCIA_API_KEY", "")

HYPERSCALERS = [
    r"amazon web services", r"\baws\b", r"\bmicrosoft\b", r"\bgoogle\b", r"\boracle\b",
    r"\bibm\b", r"\balibaba\b", r"\bhuawei\b", r"\bsalesforce\b", r"\bopenai\b",
]

KW_NUVEM = [r"microsoft ?365", r"office ?365", r"google workspace", r"google cloud", r"\bazure\b",
            r"\baws\b", r"amazon web services", r"\bnuvem\b", r"\bcloud\b", r"\biaas\b", r"\bpaas\b", r"software (as a|como) (a )?servi[çc]o", r"multi-?cloud", r"cloud broker",
            r"hospedagem de (sites?|sistemas?|aplica|dados|servidor)"]
KW_IA    = [r"intelig[eê]ncia artificial", r"\bia\b", r"machine learning", r"\bllm\b", r"copilot", r"openai"]
KW_INFRA = [r"\bdata ?center\b", r"servidor(es)? de (rede|dados|aplica)", r"servidor(es)? (f[ií]sicos?|virtuais?|blade|rack)",
            r"\bstorage\b", r"\bswitch(es)?\b", r"rede de dados", r"redes? l[oó]gicas?",
            r"cabeamento estruturado", r"link de (dados|internet)", r"conectividade"]
KW_TIC   = [r"\btic\b", r"tecnologia da informa", r"\bsoftware\b", r"licen[çc]as? de uso",
            r"sistema de informa", r"armazenamento de dados",
            r"seguran[çc]a da informa", r"cibern[eé]tic"]
MARCAS = [r"\bmicrosoft\b", r"\bazure\b", r"office ?365", r"\baws\b", r"amazon web services",
          r"google (cloud|workspace|enterprise)", r"g ?suite", r"\boracle\b", r"\bibm\b", r"\bvmware\b", r"\badobe\b", r"red ?hat", r"\bsalesforce\b", r"\bopenai\b", r"chatgpt"]
KW_EXCLUIR_IA = [r"\bcurso\b", r"treinamento", r"capacita[çc][aã]o", r"palestra", r"workshop", r"semin[aá]rio",
                 r"\boficina\b", r"execu[çc][aã]o descentralizada", r"\bted\b", r"apoio ao projeto",
                 r"funda[çc][aã]o de (apoio|desenvolvimento)"]
KW_EXCLUIR_NUVEM = [r"certifica[çc][aã]o digital", r"certificados? digita(?:l|is)", r"\be-?cpf\b", r"\be-?cnpj\b"]
KW_ABERTO = [r"open ?source", r"c[oó]digo aberto", r"software livre"]

W_PROPRIETARIO = 1.5
W_PADRAO       = 1.0
W_ABERTO       = 0.3
W_NACIONAL     = 0.0


_EVENTOS = [r"inscri[çc][aã]o", r"inscri[çc][oõ]es", r"\bcurso\b", r"treinamento", r"capacita[çc][aã]o", r"palestra",
            r"workshop", r"semin[aá]rio", r"congresso", r"\bconfer[eê]ncia\b", r"\bevento", r"patroc[ií]nio",
            r"projeto de pesquisa", r"pesquisa aplicada", r"apoiar a execu"]
KW_EXCLUIR_IA = KW_EXCLUIR_IA + _EVENTOS + [r"intelig[eê]ncia cibern"]
KW_EXCLUIR_NUVEM = KW_EXCLUIR_NUVEM + _EVENTOS
KW_BROKER = [r"cloud broker", r"multi-?cloud", r"intermedia[çc][aã]o de servi[çc]os em nuvem", r"integrador (de )?(servi[çc]os )?(em )?nuvem"]
W_BROKER = 1.0


_ACADEMICO = [r"p[óo]s-?gradua[çc][aã]o", r"mestrado", r"doutorado", r"especializa[çc][aã]o (lato|em)", r"\bvagas?\b",
              r"\bbolsas?\b", r"\binterveniente\b", r"fundação (de )?(apoio|amparo)", r"projeto de extens[aã]o",
              r"projeto de ensino"]
_EQUIPAMENTO_IA = [r"\bscanners?\b", r"raio-? ?x\b", r"inspe[çc][aã]o de (bagagens?|cargas?|ve[ií]culos)",
                   r"c[âa]meras?", r"smartphones?", r"celular(es)?", r"videoconfer", r"elevador(es)?",
                   r"dispositivos? inteligentes?", r"workstations?", r"servidor(es)? (de|para) (ia|intelig)"]
KW_EXCLUIR_IA = KW_EXCLUIR_IA + _ACADEMICO + _EQUIPAMENTO_IA
_NAO_NUVEM = [r"forense", r"extra[çc][aã]o avan[çc]ada", r"creative cloud"]
KW_EXCLUIR_NUVEM = KW_EXCLUIR_NUVEM + _ACADEMICO + _NAO_NUVEM
KW_TELEFONIA = [r"\bpabx\b", r"\bpbx\b", r"\bstfc\b", r"telef[ôo]n", r"central telef[ôo]nica", r"\bvoip\b"]
KW_EXCLUIR_NUVEM = KW_EXCLUIR_NUVEM + KW_TELEFONIA
KW_GUARDA_CHUVA = [r"servi[çc]os estrat[eé]gicos de (tic|tecnologia da informa)"]

KW_INFRA = KW_INFRA + [r"workstations?", r"servidor(es)? (de|para) (ia|intelig)"]

_FP_IA = [r"avi[áa]ria", r"refer[êe]nc ia\b", r"bengala inteligente", r"[óo]culos", r"apoio log[íi]stico",
          r"projeto intitulado", r"kits? de pcr"]
KW_EXCLUIR_IA = KW_EXCLUIR_IA + _FP_IA
KW_EXCLUIR_NUVEM = KW_EXCLUIR_NUVEM + [r"elastic cloud enterprise"]

KW_PROJETO_FUNDACAO = [r"apoio log[íi]stico,? administrativo", r"projeto intitulado", r"gest[ãa]o financeira do projeto"]

_FP_IA2 = [r"\bcursos?\b", r"\baulas?\b", r"simp[óo]sio", r"masterclass", r"\bsummit\b", r"\btickets?\b", r"oficinas?", r"desenho instrucional",
           r"centro de inova", r"n[úu]cleo de intelig", r"\bdnc\b", r"\belisa\b", r"diagn[óo]stico de ia",
           r"esc[âa]ner|scanner", r"\bnvr\b|network video recorder", r"projeto acad[êe]mico", r"\bprojeto \d{3,}",
           r"licita[çc][õo]es e contratos na administra",
           r"garantia (estendida )?dos? servidores"]
KW_EXCLUIR_IA = KW_EXCLUIR_IA + _FP_IA2
KW_EXCLUIR_NUVEM = KW_EXCLUIR_NUVEM + [r"hiperconvergent", r"vmware cloud foundation", r"\bvsan\b", r"on[- ]premises?",
                                       r"cer[a-z]*ficados? digita(?:l|is)"]
KW_INFRA = KW_INFRA + [r"hiperconvergent", r"vmware cloud foundation", r"\bvsan\b", r"garantia (estendida )?dos? servidores",
                       r"equipamentos? de seguran[çc]a de ti", r"infraestrutura de backup"]
KW_TIC = KW_TIC + [r"\bmouses?\b", r"material de ti\b", r"computador(es)?\b"]

KW_NUVEM = KW_NUVEM + [r"\bnuvens\b"]
KW_BROKER = KW_BROKER + [r"intermedia[çc][aã]o (de|para) (servi[çc]os (em )?)?nuvens?", r"\busin'?s?\b"]
KW_SUITE_NUVEM = [r"su[ií]te"]
KW_LICENCA_SW = [r"licen[çc]as? de (software|aplicativo)s?", r"subscri[çc][aã]o de licen[çc]as?"]
KW_HARDWARE_FORTE = [r"\bswitch(es)?\b", r"\bstorage\b", r"hiperconvergent", r"\bdata ?center\b"]
