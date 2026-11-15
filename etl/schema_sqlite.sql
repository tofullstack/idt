CREATE TABLE IF NOT EXISTS fornecedor (
  cnpj TEXT PRIMARY KEY, razao_social TEXT,
  origem TEXT NOT NULL CHECK (origem IN ('NACIONAL','ESTRANGEIRO','INDETERMINADO')),
  hyperscaler INTEGER NOT NULL DEFAULT 0, motivo TEXT, ubo TEXT,
  classificado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS contrato (
  id TEXT PRIMARY KEY, fonte TEXT NOT NULL, orgao TEXT, ug TEXT,
  fornecedor_cnpj TEXT REFERENCES fornecedor(cnpj), objeto TEXT, valor REAL NOT NULL,
  data_inicio TEXT NOT NULL, data_fim TEXT, categoria TEXT, peso_w REAL);
CREATE INDEX IF NOT EXISTS ix_contrato_data ON contrato(data_inicio);
CREATE INDEX IF NOT EXISTS ix_contrato_orgao ON contrato(orgao);
CREATE TABLE IF NOT EXISTS investimento_infra (
  periodo TEXT NOT NULL, valor REAL NOT NULL, fonte TEXT NOT NULL, PRIMARY KEY (periodo, fonte));
CREATE TABLE IF NOT EXISTS idt_serie (
  periodo TEXT PRIMARY KEY, numerador REAL, denominador REAL, idt REAL,
  calculado_em TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS coleta_log (
  fonte TEXT, orgao TEXT, ano INTEGER, lidos INTEGER, gravados INTEGER,
  concluido_em TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (fonte, orgao, ano));

CREATE TABLE IF NOT EXISTS amostra_descartados (
  id TEXT PRIMARY KEY, orgao TEXT, ano INTEGER, objeto TEXT, valor REAL);
