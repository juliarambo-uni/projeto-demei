"""Formato dos dados que a API recebe e devolve.

Os campos seguem exatamente o que está definido em
`integração_julia/padrao_dados.md`.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Variáveis previstas no padrão do projeto.
VARIAVEIS = (
    "irradiancia",
    "temperatura",
    "precipitacao",
    "umidade_relativa",
    "velocidade_vento",
    "direcao_vento",
)

# Unidade oficial de cada variável.
UNIDADES = {
    "irradiancia": "W/m²",
    "temperatura": "°C",
    "precipitacao": "mm",
    "umidade_relativa": "%",
    "velocidade_vento": "m/s",
    "direcao_vento": "°",
}

TipoDado = Literal["medido", "tratado", "estimado"]


class Medicao(BaseModel):
    """Um registro de medição, como sai da API."""

    estacao: str = Field(description="Código fixo da estação (ex.: gaic_mundstock)")
    timestamp: datetime = Field(description="Momento da medição, em UTC-3")
    variavel: str = Field(description="Nome padronizado da variável")
    valor: Optional[float] = Field(
        description="Valor medido. Vem nulo quando o dado está faltando."
    )
    unidade: str
    fonte: str = Field(description="GAIC, Open-Meteo ou Weather Underground")
    tipo_dado: TipoDado


class Estacao(BaseModel):
    """Os dados cadastrais de uma estação."""

    estacao: str = Field(description="Código fixo, nunca muda")
    nome: str = Field(description="Nome de exibição, pode mudar")
    latitude: float
    longitude: float
    altitude: Optional[float] = Field(default=None, description="Em metros")
    fonte: str
    variaveis: list[str] = Field(
        default_factory=list,
        description="Quais variáveis esta estação mede de fato",
    )
    ativa: bool = True


class PontoAgregado(BaseModel):
    """Um ponto já resumido por hora ou por dia.

    É o que o dashboard deve usar para períodos longos, em vez de puxar
    todos os registros brutos.
    """

    timestamp: datetime
    media: Optional[float]
    minimo: Optional[float]
    maximo: Optional[float]
    soma: Optional[float]
    quantidade: int = Field(description="Quantos registros entraram nesse ponto")


class RespostaMedicoes(BaseModel):
    """Resposta paginada da consulta de medições."""

    total: int = Field(description="Quantos registros existem no filtro inteiro")
    pagina: int
    limite: int
    dados: list[Medicao]


class RespostaAgregado(BaseModel):
    estacao: str
    variavel: str
    unidade: str
    intervalo: str
    dados: list[PontoAgregado]
