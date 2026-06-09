# dags/nogtech_pipeline.py
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Importa as funções main de cada um dos seus scripts
from scripts.extract import main as executar_extracao
from scripts.transform import main as executar_transformacao
from scripts.load import main as executar_carga

# Configurações padrão das Tasks (Tratamento de Erros e Resiliência)
default_args = {
    'owner': 'nogtech_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,                            # REQUISITO DE RESILIÊNCIA: Tenta rodar de novo se falhar
    'retry_delay': timedelta(seconds=30),     # Tempo de espera entre os retries
}

# Definição da DAG
with DAG(
    dag_id='pipeline_etl_nogtech',
    default_args=default_args,
    description='Orquestração do Pipeline ETL da NogTech (BigData)',
    schedule_interval=None,                  # Execução manual/sob demanda para a apresentação
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['bigdata', 'etl'],
) as dag:

    # 1. Task de Extração
    task_extract = PythonOperator(
        task_id='extrair_fontes_locais',
        python_callable=executar_extracao,
    )

    # 2. Task de Transformação (Consome BrasilAPI e aplica LGPD)
    task_transform = PythonOperator(
        task_id='transformar_e_enriquecer',
        python_callable=executar_transformacao,
    )

    # 3. Task de Carga (Garante a Idempotência via UPSERT)
    task_load = PythonOperator(
        task_id='carregar_fato_vendas',
        python_callable=executar_carga,
    )

    # Definição do Grafo e Dependências (Fluxo de execução)
    task_extract >> task_transform >> task_load