CREATE TABLE IF NOT EXISTS fornecedor (
  cnpj            VARCHAR(14) PRIMARY KEY,
  razao_social    TEXT,
  origem          VARCHAR(13) NOT NULL CHECK (origem IN ('NACIONAL','ESTRANGEIRO','INDETERMINADO')),
  hyperscaler     BOOLEAN NOT NULL DEFAULT FALSE,
  motivo          TEXT,
  ubo             TEXT,
  classificado_em TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contrato (
  id              TEXT PRIMARY KEY,
  fonte           VARCHAR(20) NOT NULL,
  orgao           TEXT,
  fornecedor_cnpj VARCHAR(14) REFERENCES fornecedor(cnpj),
  objeto          TEXT,
  valor           NUMERIC(18,2) NOT NULL,
  data_inicio     DATE NOT NULL,
  categoria       VARCHAR(20),
  peso_w          NUMERIC(3,2)
);
CREATE INDEX IF NOT EXISTS ix_contrato_data ON contrato(data_inicio);

CREATE TABLE IF NOT EXISTS investimento_infra (
  periodo DATE NOT NULL,
  valor   NUMERIC(18,2) NOT NULL,
  fonte   TEXT,
  PRIMARY KEY (periodo, fonte)
);

CREATE TABLE IF NOT EXISTS idt_serie (
  periodo DATE PRIMARY KEY,
  numerador NUMERIC(18,2),
  denominador NUMERIC(18,2),
  idt NUMERIC(12,4),
  calculado_em TIMESTAMP DEFAULT now()
);
