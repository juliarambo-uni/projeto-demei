"""Carrega o cadastro das estações a partir de uma planilha CSV.

O cadastro é o que alimenta o mapa do dashboard e a lista de estações da API.
Sem latitude e longitude não existe mapa.

Preencha o arquivo `estacoes_modelo.csv` e rode:

    python scripts/cadastrar_estacoes.py estacoes.csv --simular
    python scripts/cadastrar_estacoes.py estacoes.csv

Colunas esperadas:

    estacao      código fixo, minúsculo, sem espaço nem acento (ex.: gaic_centro)
    nome         nome de exibição, pode ter acento e espaço
    latitude     número negativo no Rio Grande do Sul (ex.: -28.3880)
    longitude    número negativo no Rio Grande do Sul (ex.: -53.9140)
    altitude     metros acima do nível do mar; pode ficar vazio
    fonte        GAIC, Open-Meteo ou Weather Underground
    variaveis    separadas por ponto e vírgula (ex.: temperatura;irradiancia)
    ativa        sim ou nao; vazio conta como sim

O script confere tudo antes de gravar. Se achar erro, não grava nada.
"""

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo import UpdateOne  # noqa: E402

from api.db import estacoes, testar_conexao  # noqa: E402
from api.schemas import VARIAVEIS  # noqa: E402

FONTES = ("GAIC", "Open-Meteo", "Weather Underground")

# Limites aproximados do Rio Grande do Sul. Serve para pegar o erro mais
# comum: esquecer o sinal de menos, o que joga a estação para o outro lado
# do mundo sem ninguém perceber até o mapa ficar estranho.
RS_LAT = (-33.8, -27.0)
RS_LON = (-58.0, -49.6)

# Limites do Brasil, para separar "fora do RS" (aviso) de "claramente errado".
BR_LAT = (-34.0, 5.3)
BR_LON = (-74.0, -34.0)


class ErroDeLinha(Exception):
    pass


def sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _numero(bruto: str, campo: str, obrigatorio: bool = True) -> float | None:
    texto = (bruto or "").strip().replace(",", ".")
    if texto == "":
        if obrigatorio:
            raise ErroDeLinha(f"{campo} está vazio")
        return None
    try:
        return float(texto)
    except ValueError as erro:
        raise ErroDeLinha(f"{campo} não é número: {bruto!r}") from erro


def validar(linha: dict) -> tuple[dict, list[str]]:
    """Confere uma linha. Devolve (documento, lista de avisos)."""
    avisos: list[str] = []

    codigo = (linha.get("estacao") or "").strip()
    if not codigo:
        raise ErroDeLinha("estacao (o código) está vazio")
    if codigo != sem_acento(codigo).lower().replace(" ", "_"):
        raise ErroDeLinha(
            f"código {codigo!r} tem maiúscula, acento ou espaço. "
            "Use só minúsculas, números e _ (ex.: gaic_centro)"
        )

    nome = (linha.get("nome") or "").strip()
    if not nome:
        raise ErroDeLinha("nome está vazio")

    latitude = _numero(linha.get("latitude", ""), "latitude")
    longitude = _numero(linha.get("longitude", ""), "longitude")

    if not (BR_LAT[0] <= latitude <= BR_LAT[1]):
        raise ErroDeLinha(
            f"latitude {latitude} está fora do Brasil. "
            "No RS ela é negativa, perto de -28"
        )
    if not (BR_LON[0] <= longitude <= BR_LON[1]):
        raise ErroDeLinha(
            f"longitude {longitude} está fora do Brasil. "
            "No RS ela é negativa, perto de -54"
        )
    if not (RS_LAT[0] <= latitude <= RS_LAT[1]):
        avisos.append(f"latitude {latitude} está fora do RS — confere?")
    if not (RS_LON[0] <= longitude <= RS_LON[1]):
        avisos.append(f"longitude {longitude} está fora do RS — confere?")

    altitude = _numero(linha.get("altitude", ""), "altitude", obrigatorio=False)
    if altitude is not None and not (0 <= altitude <= 1500):
        avisos.append(f"altitude {altitude} m parece estranha para a região")

    fonte = (linha.get("fonte") or "").strip()
    if fonte not in FONTES:
        raise ErroDeLinha(
            f"fonte {fonte!r} desconhecida. Use: {', '.join(FONTES)}"
        )

    bruto_variaveis = (linha.get("variaveis") or "").strip()
    if not bruto_variaveis:
        raise ErroDeLinha("variaveis está vazio — diga o que esta estação mede")

    lista_variaveis = [
        v.strip() for v in bruto_variaveis.replace(",", ";").split(";") if v.strip()
    ]
    desconhecidas = [v for v in lista_variaveis if v not in VARIAVEIS]
    if desconhecidas:
        raise ErroDeLinha(
            f"variável(is) fora do padrão: {', '.join(desconhecidas)}. "
            f"Use: {', '.join(VARIAVEIS)}"
        )

    bruto_ativa = (linha.get("ativa") or "").strip().lower()
    ativa = bruto_ativa not in ("nao", "não", "n", "false", "0")

    documento = {
        "estacao": codigo,
        "nome": nome,
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "fonte": fonte,
        "variaveis": lista_variaveis,
        "ativa": ativa,
    }
    return documento, avisos


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carrega o cadastro das estações a partir de um CSV."
    )
    parser.add_argument("arquivo", type=Path, help="Caminho do .csv")
    parser.add_argument(
        "--simular", action="store_true", help="Confere sem gravar nada"
    )
    argumentos = parser.parse_args()

    if not argumentos.arquivo.exists():
        raise SystemExit(f"Arquivo não encontrado: {argumentos.arquivo}")

    with argumentos.arquivo.open(encoding="utf-8-sig", newline="") as arquivo:
        try:
            dialeto = csv.Sniffer().sniff(arquivo.read(4096), delimiters=",;\t")
            arquivo.seek(0)
        except csv.Error:
            arquivo.seek(0)
            dialeto = csv.excel
        linhas = list(csv.DictReader(arquivo, dialect=dialeto))

    print(f"{len(linhas)} linhas no arquivo.\n")

    documentos: list[dict] = []
    erros: list[str] = []
    avisos: list[str] = []
    vistos: dict[str, int] = {}

    for indice, linha in enumerate(linhas, start=1):
        try:
            documento, avisos_linha = validar(linha)
        except ErroDeLinha as erro:
            erros.append(f"  linha {indice}: {erro}")
            continue

        codigo = documento["estacao"]
        if codigo in vistos:
            erros.append(
                f"  linha {indice}: código {codigo!r} repetido "
                f"(já apareceu na linha {vistos[codigo]})"
            )
            continue
        vistos[codigo] = indice

        documentos.append(documento)
        avisos.extend(f"  linha {indice}: {a}" for a in avisos_linha)

    if erros:
        print(f"{len(erros)} linhas com erro:")
        print("\n".join(erros))
        print("\nNada foi gravado. Corrija o arquivo e rode de novo.")
        raise SystemExit(1)

    if avisos:
        print(f"{len(avisos)} avisos (não impedem a gravação):")
        print("\n".join(avisos))
        print()

    print(f"{len(documentos)} estações válidas:\n")
    for documento in documentos:
        alt = f"{documento['altitude']:.0f} m" if documento["altitude"] else "altitude ?"
        print(
            f"  {documento['estacao']:<20} {documento['nome']:<22} "
            f"{documento['latitude']:>9.4f}, {documento['longitude']:>9.4f}  "
            f"{alt:<12} {len(documento['variaveis'])} variáveis"
        )

    if argumentos.simular:
        print("\nModo simulação: nada foi gravado.")
        return

    if not testar_conexao():
        print("\nNão consegui conectar no banco. Confere o MONGO_URI no .env")
        raise SystemExit(1)

    operacoes = [
        UpdateOne({"estacao": d["estacao"]}, {"$set": d}, upsert=True)
        for d in documentos
    ]
    resultado = estacoes.bulk_write(operacoes, ordered=False)

    print(
        f"\nPronto: {len(resultado.upserted_ids)} novas, "
        f"{resultado.modified_count} atualizadas."
    )
    print("Confere no navegador: http://localhost:8000/estacoes")


if __name__ == "__main__":
    main()
