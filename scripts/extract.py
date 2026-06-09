from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s [%(levelname)s] %(message)s",
	datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_EXPECTED_CPF_DIGITS = 11


def normalize_cpf(value: object) -> str | None:
	"""Normaliza CPF para string de 11 dígitos sem formatação.

	Retorna None se o valor for nulo ou tiver quantidade inválida de dígitos.
	"""
	if value is None:
		return None
	digits = re.sub(r"\D", "", str(value))
	if not digits:
		return None
	if len(digits) != _EXPECTED_CPF_DIGITS:
		logger.warning("CPF com número inesperado de dígitos (%d): '%s'", len(digits), value)
		return None
	return digits


def parse_brl(series: pd.Series) -> pd.Series:
	"""Converte coluna de valores em formato BRL (1.234,56) para float.

	Registra um aviso se houver valores que não puderam ser convertidos.
	"""
	converted = (
		series
		.astype(str)
		.str.replace(".", "", regex=False)
		.str.replace(",", ".", regex=False)
		.pipe(pd.to_numeric, errors="coerce")
	)
	n_failed = converted.isna().sum() - series.isna().sum()
	if n_failed > 0:
		logger.warning("%d valor(es) em 'valor_brl' não puderam ser convertidos.", n_failed)
	return converted


def read_transactions(csv_path: Path) -> pd.DataFrame:
	"""Lê e normaliza o CSV de transações."""
	logger.info("Lendo transações: %s", csv_path)
	df = pd.read_csv(csv_path, sep=";", encoding="latin-1")

	df["cpf_aluno"] = df["cpf_aluno"].map(normalize_cpf)
	df["data_transacao"] = pd.to_datetime(df["data_transacao"], errors="coerce", dayfirst=True)
	df["mes_referencia"] = df["data_transacao"].dt.to_period("M").astype(str)
	df["valor_brl"] = parse_brl(df["valor_brl"])
	df["cep_cobranca"] = (
		df["cep_cobranca"].astype(str).str.replace(r"\D", "", regex=True).str.zfill(8)
	)
	df["id_transacao"] = pd.to_numeric(df["id_transacao"], errors="coerce")

	logger.info("Transações carregadas: %d linhas", len(df))
	return df


def read_engagement(json_path: Path) -> pd.DataFrame:
	"""Lê e normaliza o JSON de engajamento."""
	logger.info("Lendo engajamento: %s", json_path)
	with json_path.open("r", encoding="utf-8") as file:
		records = json.load(file)

	df = pd.DataFrame(records)
	df["cpf_aluno"] = df["cpf_aluno"].map(normalize_cpf)
	df["mes_referencia"] = df["mes_referencia"].astype(str)

	logger.info("Engajamento carregado: %d linhas", len(df))
	return df


def build_extracted_dataset(
	transactions_path: Path,
	engagement_path: Path,
) -> pd.DataFrame:
	"""Combina transações e engajamento em um único dataset."""
	transactions = read_transactions(transactions_path)
	engagement = read_engagement(engagement_path)

	merged = transactions.merge(
		engagement,
		on=["cpf_aluno", "mes_referencia"],
		how="left",
		suffixes=("", "_engajamento"),
	)

	merged = merged.sort_values(
		["data_transacao", "cpf_aluno", "id_transacao"],
		na_position="last",
	)
	return merged.reset_index(drop=True)


def main() -> None:
	root_dir = Path(__file__).resolve().parents[1]
	data_dir = root_dir / "data"

	transactions_path = data_dir / "transacoes_nogtech.csv"
	engagement_path = data_dir / "engajamento_alunos.json"
	output_path = data_dir / "processed" / "extraido.parquet"

	try:
		for path in (transactions_path, engagement_path):
			if not path.exists():
				raise FileNotFoundError(f"Arquivo não encontrado: {path}")

		output_path.parent.mkdir(parents=True, exist_ok=True)
		dataset = build_extracted_dataset(transactions_path, engagement_path)
		dataset.to_parquet(output_path, index=False, compression="snappy")
		logger.info("Dataset salvo em: %s (%d linhas)", output_path, len(dataset))

	except FileNotFoundError as exc:
		logger.error("Arquivo de entrada ausente: %s", exc)
		raise
	except Exception as exc:
		logger.error("Erro inesperado durante a extração: %s", exc)
		raise


if __name__ == "__main__":
	main()