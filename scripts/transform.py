import json
import logging
from pathlib import Path
import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# --- FUNÇÕES AUXILIARES DE CACHE ---
def carregar_cache_json(path: Path) -> dict:
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Falha ao ler cache em %s, iniciando vazio. Erro: %s", path, e)
    return {}


def salvar_cache_json(path: Path, dados: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error("Falha ao salvar cache em %s. Erro: %s", path, e)


# --- FUNÇÕES DE TRATAMENTO DE CPF ---
def padronizar_para_mascara_cpf(valores_cpf: pd.Series) -> pd.Series:
    def aplicar_mascara(v):
        if pd.isna(v):
            return v
        v_str = str(v).strip().zfill(11)
        if len(v_str) == 11:
            return f"{v_str[:3]}.{v_str[3:6]}.{v_str[6:9]}-{v_str[9:]}"
        return v
    return valores_cpf.apply(aplicar_mascara)


def anonimizar_cpf_lgpd(valores_cpf_padronizados: pd.Series) -> pd.Series:
    def aplicar_anonimizacao(v):
        if pd.isna(v):
            return v
        v_str = str(v).strip()
        if len(v_str) == 14:
            return f"***.{v_str[4:11]}-**"
        return v
    return valores_cpf_padronizados.apply(aplicar_anonimizacao)


# --- FUNÇÃO PRINCIPAL ---
def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    input_path = root_dir / "data" / "processed" / "extraido.parquet"
    output_path = root_dir / "data" / "processed" / "transformado.parquet"
    
    cep_cache_path = root_dir / "cache" / "cep_cache.json"
    feriados_cache_path = root_dir / "cache" / "feriados_cache.json"

    if not input_path.exists():
        raise FileNotFoundError(f"O arquivo de entrada gerado pelo extract.py não existe em: {input_path}")

    logger.info("Lendo dataset extraído: %s", input_path)
    df = pd.read_parquet(input_path)

    # Limpeza básica inicial de segurança
    df = df.dropna(subset=["cpf_aluno"])
    df = df[df["cpf_aluno"].astype(str).str.strip() != ""]

    # 1. Padronização de CPF
    logger.info("Executando Requisito 3.2 - Padronização de Máscaras de CPF...")
    df["cpf_aluno"] = padronizar_para_mascara_cpf(df["cpf_aluno"])

    # Carrega caches locais
    cep_cache = carregar_cache_json(cep_cache_path)
    feriados_cache = carregar_cache_json(feriados_cache_path)

    # 2. Requisito 3.3 - BrasilAPI CEP com Cache JSON
    logger.info("Executando Requisito 3.3 - Enriquecimento de Localização via BrasilAPI...")
    bairros, cidades, estados = [], [], []

    for cep in df["cep_cobranca"]:
        cep_str = str(cep).strip() if pd.notna(cep) else ""
        cep_limpo = "".join(filter(str.isdigit, cep_str)).zfill(8)
        
        if len(cep_limpo) != 8 or cep_limpo == "00000000":
            bairros.append(None)
            cidades.append(None)
            estados.append(None)
            continue
            
        # Verifica se já está no cache e se o valor mapeado é válido
        if cep_limpo in cep_cache and cep_cache[cep_limpo].get("bairro") not in [None, "Centro / Zona Rural"]:
            dados_regiao = cep_cache[cep_limpo]
            bairros.append(dados_regiao.get("bairro"))
            cidades.append(dados_regiao.get("cidade"))
            estados.append(dados_regiao.get("estado"))
        else:
            url = f"https://brasilapi.com.br/api/cep/v2/{cep_limpo}"
            try:
                logger.info("Buscando novo CEP na BrasilAPI: %s", cep_limpo)
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Correção da chave: a API retorna 'neighborhood'
                    bairro = data.get("neighborhood")
                    cidade = data.get("city")
                    estado = data.get("state")
                    
                    if not bairro or str(bairro).strip() == "":
                        bairro = "Centro"
                    
                    cep_cache[cep_limpo] = {"bairro": bairro, "cidade": cidade, "estado": estado}
                    
                    bairros.append(bairro)
                    cidades.append(cidade)
                    estados.append(estado)
                    
                elif response.status_code == 404:
                    logger.warning("CEP %s inexistente na BrasilAPI (Status 404).", cep_limpo)
                    cep_cache[cep_limpo] = {"bairro": "Não Encontrado", "cidade": "Não Encontrado", "estado": "NF"}
                    bairros.append("Não Encontrado")
                    cidades.append("Não Encontrado")
                    estados.append("NF")
                else:
                    bairros.append(None)
                    cidades.append(None)
                    estados.append(None)
                    
            except Exception as e:
                logger.error("Erro de conexão na BrasilAPI para o CEP %s: %s", cep_limpo, e)
                bairros.append(None)
                cidades.append(None)
                estados.append(None)

    df["bairro"] = bairros
    df["cidade"] = cidades
    df["estado"] = estados

    # 3. Requisito 3.4 - BrasilAPI Feriados
    logger.info("Executando Requisito 3.4 - Análise de Calendário (Feriados) via BrasilAPI...")
    vendas_em_feriado = []

    for dt in df["data_transacao"]:
        if pd.isna(dt):
            vendas_em_feriado.append(False)
            continue
            
        dt_str = str(dt)[:10]
        ano = dt_str[:4]
        
        if ano not in feriados_cache:
            url = f"https://brasilapi.com.br/api/feriados/v1/{ano}"
            try:
                logger.info("Buscando feriados do ano %s na BrasilAPI...", ano)
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    lista_feriados = response.json()
                    feriados_cache[ano] = [f["date"] for f in lista_feriados]
                else:
                    feriados_cache[ano] = []
            except Exception as e:
                logger.error("Erro ao conectar na BrasilAPI para feriados de %s: %s", ano, e)
                feriados_cache[ano] = []

        vendas_em_feriado.append(dt_str in feriados_cache.get(ano, []))

    df["venda_em_feriado"] = vendas_em_feriado

    # 4. Requisito 3.5 - Anonimização (LGPD)
    logger.info("Executando Requisito 3.5 - Anonimização LGPD...")
    df["cpf_aluno"] = anonimizar_cpf_lgpd(df["cpf_aluno"])

    if "nome_aluno" in df.columns:
        df = df.drop(columns=["nome_aluno"])

    # Salva os arquivos de cache de volta para o disco
    salvar_cache_json(cep_cache_path, cep_cache)
    salvar_cache_json(feriados_cache_path, feriados_cache)

    # 5. Salvar o arquivo final integrado (Mantém a chave primária intacta para o Load)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False, compression="snappy")
    logger.info("Sucesso! Pipeline de Transformação concluído em: %s", output_path)


if __name__ == "__main__":
    main()