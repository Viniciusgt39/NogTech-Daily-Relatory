# NogTech Daily Relatory

Pipeline de Engenharia de Dados (ETL) para processamento diário de dados de vendas e engajamento da NogTech.

O projeto utiliza Apache Airflow para orquestração, PostgreSQL para armazenamento dos dados e arquivos Parquet como camada intermediária de persistência.

---

## Visão Geral

O pipeline executa três etapas principais:

1. Extract – Coleta dos dados brutos de vendas e engajamento.
2. Transform – Limpeza, padronização e enriquecimento dos dados.
3. Load – Carregamento dos dados transformados no PostgreSQL.

Todo o fluxo é orquestrado pelo Apache Airflow.

---

## Tecnologias Utilizadas

- Python 3
- Apache Airflow
- PostgreSQL
- Docker
- Docker Compose
- Pandas
- PyArrow
- BrasilAPI

---

## Estrutura do Projeto

```text
.
├── .github/
├── cache/
├── dags/
│   └── etl_nogtech.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── cache/
├── scripts/
│   ├── extract.py
│   ├── transform.py
│   └── load.py
├── sql/
├── .env
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Inicialização do Ambiente

### Pré-requisitos

- Docker Desktop instalado
- Docker Compose habilitado

Certifique-se de que o Docker esteja em execução antes de iniciar o projeto.

### Construir e iniciar os serviços

```bash
docker compose up --build -d
```

### Reiniciar os serviços

```bash
docker compose restart
```

### Encerrar os serviços

```bash
docker compose down
```

### Reset completo do ambiente

Remove containers, volumes e banco de dados para recriação completa do ambiente.

```bash
docker compose down -v
docker compose up --build -d
```

---

## Interfaces Disponíveis

| Serviço | URL | Credenciais |
|----------|----------|----------|
| Apache Airflow | http://localhost:8082 | airflow / airflow |
| pgAdmin 4 | http://localhost:8080 | admin@admin.com / admin |

---

## Configuração do PostgreSQL

Para conectar ao banco pelo pgAdmin:

| Parâmetro | Valor |
|------------|---------|
| Host | postgres |
| Porta | 5432 |
| Banco | nogtech_db |
| Usuário | postgres |
| Senha | postgres |

---

## Fluxo de Execução

```text
Extract
   ↓
Transform
   ↓
Load
   ↓
PostgreSQL
```

### Extract

Responsável pela coleta dos dados brutos de vendas e engajamento.

### Transform

Executa a limpeza, normalização e enriquecimento dos dados, incluindo consultas de CEP utilizando a BrasilAPI.

### Load

Realiza a carga dos dados processados para o PostgreSQL.

---

## Idempotência

A etapa de carga foi desenvolvida para permitir reprocessamentos sem gerar duplicidade de registros.

A tabela `fato_vendas` utiliza o campo:

```text
id_transacao
```

como chave natural.

Durante a carga é executado um UPSERT utilizando:

```sql
ON CONFLICT DO UPDATE
```

Com isso:

- Novos registros são inseridos.
- Registros existentes são atualizados.
- Reexecuções do pipeline mantêm a consistência dos dados.

---

## Tratamento de Falhas

### Retentativas Automáticas

A DAG está configurada com:

```python
retries = 3
retry_delay = timedelta(seconds=30)
```

Em caso de falhas temporárias, o Airflow realiza novas tentativas automaticamente.

### CEPs Não Encontrados

Quando a BrasilAPI retorna erro 404:

- Um aviso é registrado nos logs do Airflow.
- Um valor de fallback é armazenado no cache.
- O pipeline continua sua execução normalmente.

---

## Otimizações

### Cache de CEPs

As consultas à BrasilAPI são armazenadas localmente para evitar chamadas repetidas.

Benefícios:

- Redução de requisições externas.
- Melhor desempenho.
- Menor dependência de disponibilidade da API.

### Armazenamento em Parquet

Os dados processados são persistidos em formato Parquet, proporcionando:

- Alta compressão.
- Melhor desempenho de leitura.
- Menor consumo de armazenamento.

---

## Qualidade e Confiabilidade

O pipeline foi projetado seguindo princípios de:

- Idempotência
- Reprocessamento seguro
- Resiliência
- Observabilidade
- Escalabilidade

Essas características permitem execuções repetidas sem comprometer a integridade dos dados.

---
##
