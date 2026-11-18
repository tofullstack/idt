# IDT – Índice de Dependência Tecnológica

Sistema que coleta os contratos federais de TI do Compras.gov.br, classifica a origem do capital dos fornecedores (quadro de sócios da Receita Federal), calcula o IDT para 2024–2025 e mostra os resultados num painel web.

Este guia explica como instalar e rodar o sistema em outra máquina.

---

## 1. Visão geral

```
idt/
├── etl/            Python: coleta, classificação, cálculo do IDT e análise estatística
│   ├── saida/      tabelas (CSV) e figuras (PNG) geradas pela análise
│   ├── data/       listas de órgãos e caches da coleta
│   └── tests/      testes automatizados (pytest)
├── dashboard/      painel React + Vite (só exibe; não calcula nada)
│   └── public/data/dados.json   dados que o painel lê, gerados pelo etl
├── db/schema.sql   esquema para PostgreSQL (opcional)
├── docker-compose.yml          PostgreSQL via Docker (opcional)
└── banco/idt.db    banco SQLite com os dados já coletados (só no ZIP, ver seção 3)
```

Fluxo dos dados:

```
Compras.gov.br ──► pipeline.py ──► banco SQLite (contratos + fornecedores)
BrasilAPI / CNPJ.ws ─┘                   │
                                         ▼
                              analise.py ──► etl/saida/*.csv e *.png
                                         └─► dashboard/public/data/dados.json ──► painel
```

Você pode usar o sistema em três níveis:

| Objetivo | O que precisa | Tempo |
|---|---|---|
| A. Só ver o painel | Node.js | ~5 min |
| B. Refazer a análise com os dados já coletados | Python + `banco/idt.db` do ZIP | ~10 min |
| C. Coletar tudo de novo das APIs | Python + internet | várias horas |

---

## 2. Pré-requisitos

| Ferramenta | Versão | Para quê |
|---|---|---|
| [Python](https://www.python.org/downloads/) | 3.11 ou mais nova (testado na 3.12) | etl (níveis B e C) |
| [Node.js](https://nodejs.org/) | 18 ou mais nova (testado na 22) | painel |
| Git | qualquer | opcional, só se for clonar o repositório |

No Windows, marque **"Add Python to PATH"** ao instalar o Python.

Confira no terminal:

```
python --version
node --version
npm --version
```

Não é preciso instalar banco de dados: o padrão é SQLite, que já vem com o Python.

---

## 3. Instalação

### 3.1 Extrair o projeto

Extraia o ZIP numa pasta **fora** do OneDrive/Dropbox se possível (a sincronização deixa o `npm install` lento). Exemplo: `C:\projetos\idt`.

### 3.2 Colocar o banco no lugar (níveis B e C)

O sistema procura o banco em `~/idt_data/idt.db` (na pasta do usuário). Copie o arquivo do ZIP para lá:

**Windows (PowerShell), dentro da pasta `idt`:**
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\idt_data"
Copy-Item banco\idt.db "$env:USERPROFILE\idt_data\idt.db"
```

**Linux / macOS:**
```bash
mkdir -p ~/idt_data && cp banco/idt.db ~/idt_data/idt.db
```

Se preferir deixar o banco em outro lugar, defina `DATABASE_URL` no `etl/.env` (ver 3.4).

> **Atenção:** o `idt.db` contém nomes de sócios (pessoas físicas) dos fornecedores, vindos da Receita Federal. Não publique esse arquivo nem o envie a terceiros sem necessidade.

### 3.3 Ambiente Python

**Windows (PowerShell):**
```powershell
cd etl
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se o PowerShell bloquear o `Activate.ps1`, rode uma vez:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Linux / macOS:**
```bash
cd etl
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Nas próximas vezes, basta ativar o ambiente (`Activate.ps1` ou `source`) antes de rodar os scripts.

### 3.4 Configuração (`etl/.env`) – opcional

Copie o modelo: `copy .env.example .env` (Windows) ou `cp .env.example .env` (Linux/macOS).

| Variável | Padrão | Quando mudar |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<pasta do usuário>/idt_data/idt.db` | banco em outro caminho, ex.: `sqlite:///C:/dados/idt.db`, ou PostgreSQL (seção 7) |
| `TRANSPARENCIA_API_KEY` | vazio | só para a fonte `transparencia` (Portal da Transparência). A fonte principal, `compras`, não precisa de chave |

### 3.5 Verificar a instalação

Com o ambiente ativado, dentro de `etl/`:

```
python -m pytest -q
```

Resultado esperado: `59 passed`. Os testes não usam internet nem o banco real.

### 3.6 Painel

```
cd dashboard
npm install
```

---

## 4. Uso

### Nível A – ver o painel

```
cd dashboard
npm run dev
```

Abra http://localhost:5173. O painel lê `dashboard/public/data/dados.json`, que já vem no projeto.

Para gerar a versão estática (pasta `dashboard/dist/`):

```
npm run build
npm run preview      # serve o dist em http://localhost:4173
```

O `dist/` precisa ser servido por um servidor web (o `preview`, ou qualquer hospedagem estática). Abrir o `index.html` direto com duplo clique não funciona, porque o navegador bloqueia a leitura do `dados.json` via `file://`.

### Nível B – refazer a análise com os dados já coletados

Dentro de `etl/`, com o ambiente ativado:

```
python analise.py
```

Isso:
- imprime as tabelas T0–T7 no terminal;
- grava `etl/saida/t1…t7*.csv` e as figuras `fig1…fig3*.png`;
- atualiza `dashboard/public/data/dados.json` (recarregue o painel para ver).

Análises de sensibilidade (não alteram o `dados.json`):

```
python analise.py --sem-estatais           # sem Serpro, Dataprev e Telebras
python analise.py --proporcional           # valor diluído pelos meses de vigência
python analise.py --proporcional --burnin 6
python analise.py --excluir-acima 1000000000   # exclui contratos acima de R$ 1 bi
```

Os incidentes da ANPD ficam em `etl/saida/anpd_mensal.csv` (colunas `mes`, `incidentes_publico`). Se o arquivo não existir, o `analise.py` cria um modelo para preencher.

Relatório de conferência do banco (cobertura, origem dos fornecedores, indeterminados):

```
python relatorio.py
```

### Nível C – coletar os dados do zero

Precisa de internet e leva horas (as APIs públicas limitam a velocidade). A coleta pode ser interrompida e retomada: órgão/ano já concluídos são pulados.

```
# 1. descobrir os órgãos federais (gera etl/data/orgaos_validados.csv)
python discover_orgaos.py uasgs
python discover_orgaos.py orgaos
python discover_orgaos.py probe --anos 2024 2025
python discover_orgaos.py resumo

# 2. coletar contratos de todos os órgãos validados e classificar os fornecedores
python pipeline.py validados 2024 2025

#    ou só um órgão:
python pipeline.py orgao compras <codigoOrgao> 2024 2025

# 3. revisões opcionais
python pipeline.py reclassificar        # tenta de novo os fornecedores INDETERMINADOS
python pipeline.py recategorizar        # reaplica as regras de categoria após mudar config.py

# 4. análise e painel
python analise.py
```

O ZIP já traz `etl/data/orgaos_validados.csv`, então o passo 1 pode ser pulado.

Para começar com um banco vazio, use um caminho novo em `DATABASE_URL` (ou renomeie o `idt.db` existente). As tabelas são criadas automaticamente.

---

## 5. Scripts do `etl/`

| Script | Função |
|---|---|
| `pipeline.py` | coleta + normalização + classificação de fornecedores + gravação no banco |
| `coleta_compras.py` | cliente da API de contratos do Compras.gov.br |
| `collectors/transparencia.py` | cliente da API do Portal da Transparência (precisa de chave) |
| `classifier.py` | origem do capital (NACIONAL / ESTRANGEIRO / INDETERMINADO) pelo QSA, via BrasilAPI e publica.cnpj.ws |
| `enrich.py`, `config.py` | categorias (NUVEM, IA, INFRA, TIC, OUTRO), lista de hyperscalers e palavras-chave |
| `normalize.py` | padroniza os registros das APIs |
| `analise.py` | IDT, tabelas A/B/C, concentração (HHI), Spearman com a ANPD, figuras |
| `exportar_dashboard.py` | gera o `dados.json` do painel (chamado pelo `analise.py`) |
| `rotular.py` | validação manual da classificação (amostra, rotulagem cega, kappa) |
| `discover_orgaos.py` | descobre e valida os códigos de órgão federais |
| `relatorio.py` | resumo do banco para conferência |
| `calc_idt.py`, `idt.py`, `load_invest.py` | versão anterior do IDT com denominador externo (investimento em infraestrutura) |
| `diag_*.py`, `ver_*.py`, `testar_cnpj.py`, `buscar_fornecedor.py`, `sample.py`, `qa_cobertura.py`, `medir_atual.py` | diagnósticos pontuais usados no desenvolvimento |

---

## 6. Problemas comuns

| Sintoma | Causa / solução |
|---|---|
| `python` não é reconhecido | Python fora do PATH. Reinstale marcando "Add Python to PATH", ou use `py` no lugar de `python` |
| `ModuleNotFoundError` | ambiente virtual não ativado, ou falta rodar `pip install -r requirements.txt` |
| `analise.py` mostra 0 contratos | o banco não está em `~/idt_data/idt.db` (seção 3.2) ou `DATABASE_URL` aponta para outro arquivo |
| Painel mostra "Dados não encontrados" | falta `dashboard/public/data/dados.json`; rode `python analise.py` |
| Painel com faixa vermelha "DADOS DE TESTE" | o `dados.json` é sintético (gerado pelos testes); rode `python analise.py` |
| `npm install` muito lento ou com erro `EPERM` | pasta dentro do OneDrive; mova o projeto para fora ou pause a sincronização |
| Coleta para com HTTP 429/5xx | limite das APIs públicas; espere e rode o mesmo comando, ele continua de onde parou |

---

## 7. PostgreSQL (opcional)

O SQLite basta. Para usar PostgreSQL:

```
docker compose up -d                 # sobe o Postgres com db/schema.sql
pip install psycopg2-binary
```

E no `etl/.env`:

```
DATABASE_URL=postgresql://idt:idt@localhost:5432/idt
```

Os dados do `idt.db` não são migrados automaticamente; com Postgres é preciso coletar de novo (nível C).

---

## 8. Mais informações

- Requisitos, arquitetura e definição do IDT: [dashboard/README.md](dashboard/README.md)
- Definição resumida: IDT = 100 × valor dependente ÷ valor total da família TIC (NUVEM, IA, INFRA, TIC), na janela 2024-01 a 2025-12.
