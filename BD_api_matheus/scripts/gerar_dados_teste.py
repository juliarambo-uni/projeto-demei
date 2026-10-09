"""Gera dados falsos no formato do projeto, para testar o banco e a API.

Serve para você trabalhar sem depender da entrega do ETL. Quando os dados
reais chegarem, é só apagar a collection e carregar os de verdade.

Uso:
    python scripts/gerar_dados_teste.py              # 30 dias
    python scripts/gerar_dados_teste.py --dias 90
    python scripts/gerar_dados_teste.py --limpar     # apaga antes de gerar
"""

import argparse
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Permite rodar este script de qualquer lugar: coloca a raiz do projeto
# (a pasta BD_api_matheus) no caminho de busca do Python.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo import UpdateOne  # noqa: E402

from api.db import (  # noqa: E402
    TZ_PROJETO,
    criar_indices,
    estacoes,
    medicoes,
    para_utc,
    testar_conexao,
)
from api.schemas import UNIDADES  # noqa: E402

# Estações de exemplo, com coordenadas aproximadas de Ijuí/RS.
# ATENÇÃO: estas coordenadas são inventadas para teste.
# Substituir pelas reais quando o grupo confirmar.
ESTACOES_TESTE = [
    {
        "estacao": "gaic_mundstock",
        "nome": "Mundstock",
        "latitude": -28.3920,
        "longitude": -53.9180,
        "altitude": 335.0,
        "fonte": "GAIC",
        "variaveis": ["irradiancia", "temperatura", "umidade_relativa"],
        "ativa": True,
    },
    {
        "estacao": "gaic_centro",
        "nome": "Centro",
        "latitude": -28.3880,
        "longitude": -53.9140,
        "altitude": 348.0,
        "fonte": "GAIC",
        "variaveis": ["irradiancia", "temperatura", "umidade_relativa"],
        "ativa": True,
    },
    {
        "estacao": "gaic_storch",
        "nome": "Storch",
        "latitude": -28.4050,
        "longitude": -53.9320,
        "altitude": 320.0,
        "fonte": "GAIC",
        "variaveis": ["irradiancia", "temperatura"],
        "ativa": True,
    },
    {
        "estacao": "om_ijui",
        "nome": "Ijuí (Open-Meteo)",
        "latitude": -28.3878,
        "longitude": -53.9147,
        "altitude": 340.0,
        "fonte": "Open-Meteo",
        "variaveis": [
            "temperatura",
            "umidade_relativa",
            "precipitacao",
            "velocidade_vento",
            "direcao_vento",
        ],
        "ativa": True,
    },
    {
        "estacao": "wu_floresta",
        "nome": "Floresta (Weather Underground)",
        "latitude": -28.3760,
        "longitude": -53.9050,
        "altitude": 352.0,
        "fonte": "Weather Underground",
        "variaveis": ["temperatura", "umidade_relativa", "precipitacao"],
        "ativa": True,
    },
]

INTERVALO_MINUTOS = 15

# Chance de um registro vir sem valor, simulando falha de medição.
# Isso é de propósito: a API e o dashboard precisam aguentar valor nulo.
CHANCE_FALHA = 0.03


def valor_simulado(variavel: str, momento: datetime) -> float:
    """Gera um valor plausível para a variável, de acordo com a hora do dia."""
    hora = momento.hour + momento.minute / 60
    dia_do_ano = momento.timetuple().tm_yday

    # Variação ao longo do ano (verão mais quente no hemisfério sul).
    estacao_ano = math.cos((dia_do_ano - 15) / 365 * 2 * math.pi)

    if variavel == "irradiancia":
        # Curva solar: zero à noite, pico ao meio-dia.
        if hora < 6 or hora > 19:
            return 0.0
        curva = math.sin((hora - 6) / 13 * math.pi)
        nuvens = random.uniform(0.35, 1.0)
        return round(max(0.0, 1050 * curva * nuvens), 1)

    if variavel == "temperatura":
        base = 19 + 5 * estacao_ano
        ciclo = 7 * math.sin((hora - 9) / 24 * 2 * math.pi)
        return round(base + ciclo + random.uniform(-1.5, 1.5), 1)

    if variavel == "umidade_relativa":
        ciclo = -20 * math.sin((hora - 9) / 24 * 2 * math.pi)
        return round(min(100.0, max(25.0, 70 + ciclo + random.uniform(-6, 6))), 1)

    if variavel == "precipitacao":
        # Na maior parte do tempo não chove.
        if random.random() < 0.94:
            return 0.0
        return round(random.uniform(0.2, 9.0), 1)

    if variavel == "velocidade_vento":
        return round(max(0.0, random.gauss(2.6, 1.3)), 1)

    if variavel == "direcao_vento":
        return round(random.uniform(0, 360), 0)

    return 0.0


def gerar(dias: int, limpar: bool) -> None:
    if not testar_conexao():
        print("Não consegui conectar no banco. Confere o MONGO_URI no .env")
        raise SystemExit(1)

    print("Criando índices...")
    criar_indices()

    if limpar:
        print("Apagando dados anteriores...")
        medicoes.delete_many({})
        estacoes.delete_many({})

    print("Cadastrando estações...")
    for estacao in ESTACOES_TESTE:
        estacoes.update_one(
            {"estacao": estacao["estacao"]}, {"$set": estacao}, upsert=True
        )

    fim = datetime.now(TZ_PROJETO).replace(second=0, microsecond=0)
    fim -= timedelta(minutes=fim.minute % INTERVALO_MINUTOS)
    inicio = fim - timedelta(days=dias)

    print(f"Gerando medições de {inicio:%d/%m/%Y} até {fim:%d/%m/%Y}...")

    operacoes: list[UpdateOne] = []
    total = 0
    momento = inicio

    while momento <= fim:
        for estacao in ESTACOES_TESTE:
            for variavel in estacao["variaveis"]:
                falhou = random.random() < CHANCE_FALHA
                documento = {
                    "estacao": estacao["estacao"],
                    "timestamp": para_utc(momento),
                    "variavel": variavel,
                    "valor": None if falhou else valor_simulado(variavel, momento),
                    "unidade": UNIDADES[variavel],
                    "fonte": estacao["fonte"],
                    "tipo_dado": "medido",
                }
                # upsert usa a mesma chave do índice único: rodar duas vezes
                # não duplica nada.
                operacoes.append(
                    UpdateOne(
                        {
                            "estacao": documento["estacao"],
                            "timestamp": documento["timestamp"],
                            "variavel": documento["variavel"],
                            "fonte": documento["fonte"],
                        },
                        {"$set": documento},
                        upsert=True,
                    )
                )

        if len(operacoes) >= 5000:
            medicoes.bulk_write(operacoes, ordered=False)
            total += len(operacoes)
            print(f"  {total} registros gravados...")
            operacoes = []

        momento += timedelta(minutes=INTERVALO_MINUTOS)

    if operacoes:
        medicoes.bulk_write(operacoes, ordered=False)
        total += len(operacoes)

    print(f"\nPronto: {total} registros, {len(ESTACOES_TESTE)} estações.")
    print("Suba a API com:  uvicorn api.main:app --reload")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera dados falsos para teste")
    parser.add_argument("--dias", type=int, default=30, help="Quantos dias gerar")
    parser.add_argument(
        "--limpar", action="store_true", help="Apaga os dados antes de gerar"
    )
    argumentos = parser.parse_args()
    gerar(argumentos.dias, argumentos.limpar)
