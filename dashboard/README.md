# Dashboard do IDT

Painel de visualização do Índice de Dependência Tecnológica (IDT) dos contratos federais de TI (2024–2025). É a camada de aplicação do sistema; o cálculo fica no backend em Python (`etl/`).

## Requisitos

**Funcionais**
- RF1. Mostrar o IDT do biênio (valor dependente ÷ valor total de TI, em %) e os cenários de sensibilidade W1 e W2.
- RF2. Mostrar o IDT mensal, com o IDT do biênio como referência.
- RF3. Mostrar a participação de A, B e C por categoria (NUVEM, IA, INFRA, TIC, Nuvem + IA, Família TIC).
- RF4. Mostrar os maiores fornecedores de nuvem e IA, o HHI e a participação dos 3 maiores.
- RF5. Mostrar o IDT mensal ao lado dos incidentes notificados à ANPD, em gráficos separados (sem eixo duplo), e as correlações de Spearman com IC de 95%.
- RF6. Alternar entre "com estatais" e "sem estatais" (Serpro, Dataprev, Telebras) em todos os indicadores.
- RF7. Oferecer cada gráfico também como tabela.
- RF8. Exibir sempre as limitações e avisar quando os dados forem sintéticos ou não existirem.

**Não funcionais**
- RNF1. Reprodutível: os números do painel vêm de um único arquivo (`public/data/dados.json`) gerado pelo `analise.py`.
- RNF2. O frontend não calcula indicadores, só exibe.
- RNF3. Funciona em tela de celular e em modo claro e escuro; cores validadas para daltonismo.
- RNF4. Estático: roda sem servidor de aplicação.

## Arquitetura (3 camadas, padrão MVC)

```
Coleta (etl/)         Compras.gov.br API  ->  contratos
                      BrasilAPI / publica.cnpj.ws -> QSA dos fornecedores
Processamento (etl/)  classificação (categoria), origem do capital, SQLite
Aplicação             analise.py  -> IDT, A/B/C, concentração, Spearman
                      exportar_dashboard.py -> dashboard/public/data/dados.json
                      dashboard (React + Vite) -> leitura e visualização
```

- **Model:** `dados.json` (saída do backend em Python).
- **View:** componentes React em `src/App.jsx` (gráficos com Recharts) e `src/styles.css`.
- **Controller:** estado do filtro com/sem estatais e carga do JSON (`App`).

O backend é Python (não há API HTTP): os dados mudam em lote, 24 meses, então uma API em Spring Boot não traria ganho. Decisão de arquitetura registrada no texto do TCC.

## Fonte dos dados

- Contratos: Compras.gov.br (módulo contratos), campo `dataVigenciaInicial` define o mês.
- Quadro de sócios (QSA): Receita Federal, via BrasilAPI e, na falha, publica.cnpj.ws.
- Incidentes: série mensal da ANPD em `etl/saida/anpd_mensal.csv`.

## Definição do IDT

IDT = 100 × valor dependente ÷ valor total da família TIC (NUVEM, IA, INFRA e TIC). Dependente = sócio estrangeiro na cadeia societária (B, que inclui hyperscalers) ou marca/intermediação de hyperscaler via fornecedor nacional (C). Cenários de sensibilidade (pesos não calibrados): W1 = hyperscaler 1,5; W2 = dependência indireta 0,5.

## Como reproduzir (Windows, PowerShell)

```powershell
cd etl
python -m pytest -q
python analise.py            # gera saida/*.csv e ../dashboard/public/data/dados.json

cd ..\dashboard
npm install
npm run dev                  # abre o painel em http://localhost:5173
npm run build                # versão estática em dist/
```

Se `dados.json` não existir, o painel mostra instruções. Dados sintéticos (só para teste) aparecem com faixa vermelha.
