import csv
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent
PASTA_DADOS = PASTA_PROJETO / "dados_brutos"

ARQUIVO_CONSOLIDADO = (
    PASTA_DADOS
    / "weather_underground_IIJU2_2026-10-01_a_2026-10-08.csv"
)


def obter_dados():
    """Lê e retorna os dados consolidados dos CSVs."""

    if not ARQUIVO_CONSOLIDADO.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {ARQUIVO_CONSOLIDADO}"
        )

    with open(
        ARQUIVO_CONSOLIDADO,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as arquivo:
        leitor = csv.DictReader(arquivo)
        return list(leitor)
