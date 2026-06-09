# NogTech Daily Relatory

Pipeline de dados para ingestão, transformação e carga em PostgreSQL, orquestrado com Airflow e usando arquivos Parquet como camada intermediária.

## Arquitetura

- **Entrada**: `data/transacoes_nogtech.csv` e `data/engajamento_alunos.json`
- **Extração**: `scripts/extract.py` gera `data/processed/extraido.parquet`
- **Transformação**: `scripts/transform.py` enriquece os dados com BrasilAPI e gera `data/processed/transformado.parquet`
- **Carga**: `scripts/load.py` faz o UPSERT na tabela `fato_vendas` no PostgreSQL
- **Orquestração**: `dags/nogtech_pipeline.py` executa o fluxo no Airflow

## Inicialização do ambiente

1. Crie o arquivo `.env` a partir de `.env.example`.
2. Suba os serviços com:

```bash
docker compose up -d
```

3. Se necessário, acompanhe os logs:

```bash
docker compose logs -f airflow-webserver
docker compose logs -f airflow-scheduler
docker compose logs -f postgres
```

## Portas de acesso

- **Airflow Web UI**: `http://localhost:8082`
- **pgAdmin**: `http://localhost:8080`
- **PostgreSQL**: `localhost:5432`

## Estratégia de idempotência e falhas

O pipeline foi desenhado para ser executado mais de uma vez sem duplicar dados. A chave natural é `id_transacao`, usada como `PRIMARY KEY` na tabela `fato_vendas`. Na carga, o [`scripts/load.py`](scripts/load.py) aplica `UPSERT` com `ON CONFLICT (id_transacao) DO UPDATE`, então uma mesma transação é inserida na primeira execução e atualizada nas próximas, em vez de gerar duplicidade.

O processamento também reduz o impacto de falhas ao usar arquivos Parquet intermediários. Assim, se uma etapa falhar, as etapas anteriores já materializadas podem ser reutilizadas sem refazer toda a extração. Além disso:

- `scripts/extract.py` valida arquivos de entrada e normaliza campos antes de gravar o Parquet.
- `scripts/transform.py` usa cache local para evitar chamadas repetidas à BrasilAPI.
- `scripts/load.py` converte tipos para valores nativos do Python e encerra a execução com erro explícito se a carga no banco falhar.

## Banco de dados

O projeto usa PostgreSQL por ser compatível com o Airflow, suportar constraints e UPSERT de forma nativa, além de se integrar bem ao fluxo analítico do projeto.

## Observações

- O arquivo `.env` contém valores locais de execução e não deve ser versionado.
- O arquivo `.env.example` serve como modelo para novos ambientes.
