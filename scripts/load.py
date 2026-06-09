# scripts/load.py
import os
import logging
from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Cria a conexão com o banco de dados Postgres utilizando variáveis de ambiente."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "nogtech_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        port=os.getenv("DB_PORT", "5432")
    )


def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    input_path = root_dir / "data" / "processed" / "transformado.parquet"

    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo transformado não encontrado para carga: {input_path}")

    logger.info("Lendo dados transformados do arquivo Parquet...")
    df = pd.read_parquet(input_path)
    
    # Tratamento de tipos para o Postgres
    if "data_transacao" in df.columns:
        df["data_transacao"] = pd.to_datetime(df["data_transacao"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    # Normaliza tipos para escalar em tipos nativos do Python antes do psycopg2.
    # Isso evita problemas com numpy.bool_, float NaN em colunas inteiras e outros tipos pandas.
    for col in ("aulas_assistidas", "tempo_plataforma_min"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").apply(
                lambda v: int(v) if pd.notna(v) else None
            )

    if "venda_em_feriado" in df.columns:
        df["venda_em_feriado"] = df["venda_em_feriado"].apply(
            lambda v: bool(v) if pd.notna(v) else None
        )

    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    # Garante a ordem exata das colunas para bater com o SQL de INSERT
    colunas_ordenadas = [
        "id_transacao", "cpf_aluno", "data_transacao", "valor", "cep_cobranca",
        "mes_referencia", "aulas_assistidas", "tempo_plataforma_min",
        "bairro", "cidade", "estado", "venda_em_feriado"
    ]
    
    for col in colunas_ordenadas:
        if col not in df.columns:
            df[col] = None
            
    df = df[colunas_ordenadas]

    # Substitui NaNs remanescentes por None puro do Python (NULL no banco)
    df = df.astype(object).where(pd.notnull(df), None)

    # Converte o DataFrame em uma lista de tuplas de tipos nativos (Python puro)
    # Isso evita problemas com numpy.bool_ e valores não serializáveis pelo psycopg2.
    registros = [tuple(d[col] for col in colunas_ordenadas) for d in df.to_dict(orient="records")]

    # Query de Carga com a estratégia de Idempotência (UPSERT)
    query = """
        INSERT INTO fato_vendas (
            id_transacao, cpf_aluno, data_transacao, valor, cep_cobranca, 
            mes_referencia, aulas_assistidas, tempo_plataforma_min, 
            bairro, cidade, estado, venda_em_feriado
        ) VALUES %s
        ON CONFLICT (id_transacao) DO UPDATE SET
            cpf_aluno = EXCLUDED.cpf_aluno,
            data_transacao = EXCLUDED.data_transacao,
            valor = EXCLUDED.valor,
            cep_cobranca = EXCLUDED.cep_cobranca,
            mes_referencia = EXCLUDED.mes_referencia,
            aulas_assistidas = EXCLUDED.aulas_assistidas,
            tempo_plataforma_min = EXCLUDED.tempo_plataforma_min,
            bairro = EXCLUDED.bairro,
            cidade = EXCLUDED.cidade,
            estado = EXCLUDED.estado,
            venda_em_feriado = EXCLUDED.venda_em_feriado;
    """

    logger.info("Conectando ao banco de dados para iniciar a carga...")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                logger.info("Executando UPSERT em lote de %d linhas na tabela fato_vendas...", len(registros))
                execute_values(cur, query, registros)
                conn.commit()
                logger.info("Carga concluída com sucesso! Idempotência garantida.")
    except Exception as e:
        logger.error("Erro crítico durante a carga no banco de dados: %s", e)
        raise


if __name__ == "__main__":
    main()