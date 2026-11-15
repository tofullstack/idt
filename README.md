# IDT – Índice de Dependência Tecnológica

## Subir
    docker compose up -d
    cd etl && python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt && cp .env.example .env   # preencher a chave
    PYTHONPATH=. pytest
    python sample.py compras <codigoOrgao>           # inspeciona campos reais
    python pipeline.py compras <codigoOrgao> 2020-01-01 2025-12-31
    python load_invest.py data/investimento.csv
    python calc_idt.py

## Roteiro (alinhado ao cronograma)
1. [feito] schema, coleta Transparência, classificador QSA/UBO, W, IDT, estatística
2. [feito] Coletor Compras.gov.br, pipeline unificado, carga do denominador (CSV), calc_idt
3. API Spring Boot (Controller/Service/Repository) lendo idt_serie
4. Dashboard React/Vite (série do IDT, ranking de órgãos, hyperscalers, H1/H2)
