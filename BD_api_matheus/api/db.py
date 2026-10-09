"""Conexão com o MongoDB e criação dos índices.

Observação importante sobre datas:

O MongoDB sempre guarda datas em UTC internamente. Para não misturar fuso,
o projeto adota a seguinte regra:

- ao GRAVAR: converte o horário local (UTC-3) para UTC e grava;
- ao LER: converte de volta para UTC-3 antes de devolver na API.

Assim o banco fica consistente e a API continua respondendo no formato
definido em `padrao_dados.md`: YYYY-MM-DDTHH:MM:SS-03:00
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pymongo import ASCENDING, MongoClient

from api.config import (
    COLLECTION_ESTACOES,
    COLLECTION_MEDICOES,
    FUSO_PROJETO,
    MONGO_DB,
    MONGO_URI,
)

TZ_PROJETO = ZoneInfo(FUSO_PROJETO)

_cliente = MongoClient(MONGO_URI, tz_aware=True, tzinfo=timezone.utc)
banco = _cliente[MONGO_DB]

medicoes = banco[COLLECTION_MEDICOES]
estacoes = banco[COLLECTION_ESTACOES]


def para_utc(data: datetime) -> datetime:
    """Recebe uma data (com ou sem fuso) e devolve em UTC.

    Se a data vier sem fuso, assume que está no fuso do projeto (UTC-3).
    """
    if data.tzinfo is None:
        data = data.replace(tzinfo=TZ_PROJETO)
    return data.astimezone(timezone.utc)


def para_fuso_projeto(data: datetime) -> datetime:
    """Recebe uma data em UTC e devolve no fuso do projeto (UTC-3)."""
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(TZ_PROJETO)


def criar_indices() -> None:
    """Cria os índices das collections.

    Pode ser executado quantas vezes for necessário: se o índice já existe,
    o MongoDB simplesmente ignora.
    """
    # Índice único: impede registros duplicados.
    # Se o ETL rodar duas vezes com os mesmos dados, o banco não duplica.
    medicoes.create_index(
        [
            ("estacao", ASCENDING),
            ("timestamp", ASCENDING),
            ("variavel", ASCENDING),
            ("fonte", ASCENDING),
        ],
        unique=True,
        name="idx_unico_medicao",
    )

    # Índice de consulta: é o que a API usa para filtrar por estação,
    # variável e período. Sem ele as consultas ficam lentas.
    medicoes.create_index(
        [
            ("estacao", ASCENDING),
            ("variavel", ASCENDING),
            ("timestamp", ASCENDING),
        ],
        name="idx_consulta",
    )

    # Índice por período, para consultas que não filtram estação.
    medicoes.create_index([("timestamp", ASCENDING)], name="idx_timestamp")

    # Cada estação aparece uma única vez na collection de estações.
    estacoes.create_index([("estacao", ASCENDING)], unique=True, name="idx_estacao")


def testar_conexao() -> bool:
    """Verifica se o banco está respondendo."""
    try:
        _cliente.admin.command("ping")
        return True
    except Exception:
        return False
