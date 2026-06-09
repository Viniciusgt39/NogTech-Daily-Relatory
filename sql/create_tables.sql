-- sql/create_tables.sql
CREATE TABLE IF NOT EXISTS fato_vendas (
    id_transacao VARCHAR(50) PRIMARY KEY,
    cpf_aluno VARCHAR(14),
    data_transacao TIMESTAMP,
    valor NUMERIC(10, 2),
    cep_cobranca VARCHAR(8),
    mes_referencia VARCHAR(7),
    aulas_assistidas INTEGER,
    tempo_plataforma_min INTEGER,
    bairro VARCHAR(100),
    cidade VARCHAR(100),
    estado VARCHAR(2),
    venda_em_feriado BOOLEAN
);