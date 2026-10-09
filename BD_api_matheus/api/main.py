"""API de disponibilização dos dados meteorológicos.

Esta é a camada que fica entre o banco de dados e o dashboard.
O dashboard (e qualquer outro sistema no futuro) consulta estes endpoints
em vez de acessar o MongoDB diretamente.

Para rodar:
    uvicorn api.main:app --reload

A documentação interativa fica em http://localhost:8000/docs
"""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api.config import LIMITE_MAXIMO, LIMITE_PADRAO
from api.db import estacoes, medicoes, para_fuso_projeto, para_utc, testar_conexao
from api.schemas import (
    UNIDADES,
    VARIAVEIS,
    Estacao,
    Medicao,
    PontoAgregado,
    RespostaAgregado,
    RespostaMedicoes,
)

app = FastAPI(
    title="API de Dados Meteorológicos — DEMEI",
    description=(
        "Disponibiliza os dados meteorológicos padronizados de Ijuí/RS "
        "para o dashboard e outros sistemas."
    ),
    version="0.1.0",
)

# Libera o acesso para o dashboard em Streamlit.
# Em produção, trocar "*" pelo endereço real do dashboard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _formatar_medicao(documento: dict) -> Medicao:
    """Converte um documento do Mongo no formato de saída da API."""
    return Medicao(
        estacao=documento["estacao"],
        timestamp=para_fuso_projeto(documento["timestamp"]),
        variavel=documento["variavel"],
        valor=documento.get("valor"),
        unidade=documento.get("unidade", UNIDADES.get(documento["variavel"], "")),
        fonte=documento["fonte"],
        tipo_dado=documento.get("tipo_dado", "medido"),
    )


def _montar_filtro(
    estacao: Optional[str],
    variavel: Optional[str],
    fonte: Optional[str],
    inicio: Optional[datetime],
    fim: Optional[datetime],
) -> dict:
    """Monta o filtro da consulta ao Mongo a partir dos parâmetros da URL."""
    filtro: dict = {}

    if estacao:
        filtro["estacao"] = estacao
    if variavel:
        filtro["variavel"] = variavel
    if fonte:
        filtro["fonte"] = fonte

    if inicio or fim:
        periodo = {}
        if inicio:
            periodo["$gte"] = para_utc(inicio)
        if fim:
            periodo["$lte"] = para_utc(fim)
        filtro["timestamp"] = periodo

    return filtro


@app.get("/saude", tags=["sistema"])
def saude() -> dict:
    """Diz se a API está no ar e se o banco está respondendo."""
    banco_ok = testar_conexao()
    return {
        "api": "ok",
        "banco": "ok" if banco_ok else "sem conexão",
    }


@app.get("/variaveis", tags=["metadados"])
def listar_variaveis() -> list[dict]:
    """Lista as variáveis do projeto e suas unidades."""
    return [{"variavel": v, "unidade": UNIDADES[v]} for v in VARIAVEIS]


@app.get("/estacoes", response_model=list[Estacao], tags=["estações"])
def listar_estacoes(
    apenas_ativas: bool = Query(True, description="Esconde estações desativadas"),
) -> list[Estacao]:
    """Lista as estações com localização e variáveis disponíveis.

    É daqui que o dashboard tira os pontos do mapa.
    """
    filtro = {"ativa": True} if apenas_ativas else {}
    documentos = estacoes.find(filtro, {"_id": 0}).sort("estacao", 1)
    return [Estacao(**documento) for documento in documentos]


@app.get("/estacoes/{codigo}", response_model=Estacao, tags=["estações"])
def buscar_estacao(codigo: str) -> Estacao:
    """Busca uma estação pelo código."""
    documento = estacoes.find_one({"estacao": codigo}, {"_id": 0})
    if not documento:
        raise HTTPException(status_code=404, detail="Estação não encontrada")
    return Estacao(**documento)


@app.get("/medicoes", response_model=RespostaMedicoes, tags=["medições"])
def listar_medicoes(
    estacao: Optional[str] = Query(None, description="Código da estação"),
    variavel: Optional[str] = Query(None, description="Nome da variável"),
    fonte: Optional[str] = Query(None, description="GAIC, Open-Meteo, ..."),
    inicio: Optional[datetime] = Query(
        None, description="Início do período (ex.: 2026-10-01T00:00:00-03:00)"
    ),
    fim: Optional[datetime] = Query(None, description="Fim do período"),
    limite: int = Query(LIMITE_PADRAO, ge=1, le=LIMITE_MAXIMO),
    pagina: int = Query(1, ge=1),
) -> RespostaMedicoes:
    """Consulta os dados brutos, com filtro de estação, variável e período.

    Atenção: para períodos longos, use `/medicoes/agregado`. Puxar um ano
    inteiro de dados brutos trava o dashboard.
    """
    if variavel and variavel not in VARIAVEIS:
        raise HTTPException(
            status_code=400,
            detail=f"Variável desconhecida. Use uma destas: {', '.join(VARIAVEIS)}",
        )

    filtro = _montar_filtro(estacao, variavel, fonte, inicio, fim)
    total = medicoes.count_documents(filtro)

    documentos = (
        medicoes.find(filtro, {"_id": 0})
        .sort("timestamp", 1)
        .skip((pagina - 1) * limite)
        .limit(limite)
    )

    return RespostaMedicoes(
        total=total,
        pagina=pagina,
        limite=limite,
        dados=[_formatar_medicao(d) for d in documentos],
    )


@app.get("/medicoes/ultima", response_model=Medicao, tags=["medições"])
def ultima_medicao(
    estacao: str = Query(..., description="Código da estação"),
    variavel: str = Query(..., description="Nome da variável"),
) -> Medicao:
    """Devolve a medição mais recente de uma estação.

    É o endpoint para o painel de "tempo real" do dashboard.
    """
    documento = medicoes.find_one(
        {"estacao": estacao, "variavel": variavel, "valor": {"$ne": None}},
        {"_id": 0},
        sort=[("timestamp", -1)],
    )
    if not documento:
        raise HTTPException(status_code=404, detail="Nenhuma medição encontrada")
    return _formatar_medicao(documento)


@app.get("/medicoes/agregado", response_model=RespostaAgregado, tags=["medições"])
def medicoes_agregadas(
    estacao: str = Query(..., description="Código da estação"),
    variavel: str = Query(..., description="Nome da variável"),
    inicio: Optional[datetime] = Query(None),
    fim: Optional[datetime] = Query(None),
    intervalo: str = Query("dia", pattern="^(hora|dia|mes)$"),
) -> RespostaAgregado:
    """Devolve os dados já resumidos por hora, dia ou mês.

    O cálculo acontece dentro do MongoDB, então volta pouco dado pela rede.
    É isto que o dashboard deve usar para gráficos de período longo.
    """
    if variavel not in VARIAVEIS:
        raise HTTPException(
            status_code=400,
            detail=f"Variável desconhecida. Use uma destas: {', '.join(VARIAVEIS)}",
        )

    filtro = _montar_filtro(estacao, variavel, None, inicio, fim)
    # Valores nulos não entram na média.
    filtro["valor"] = {"$ne": None}

    formato = {"hora": "%Y-%m-%dT%H:00:00", "dia": "%Y-%m-%d", "mes": "%Y-%m"}[intervalo]

    etapas = [
        {"$match": filtro},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": formato,
                        "date": "$timestamp",
                        "timezone": "America/Sao_Paulo",
                    }
                },
                "media": {"$avg": "$valor"},
                "minimo": {"$min": "$valor"},
                "maximo": {"$max": "$valor"},
                "soma": {"$sum": "$valor"},
                "quantidade": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    resultado = list(medicoes.aggregate(etapas))

    pontos = []
    for linha in resultado:
        rotulo = linha["_id"]
        if intervalo == "mes":
            rotulo = f"{rotulo}-01T00:00:00"
        elif intervalo == "dia":
            rotulo = f"{rotulo}T00:00:00"
        pontos.append(
            PontoAgregado(
                timestamp=datetime.fromisoformat(f"{rotulo}-03:00"),
                media=round(linha["media"], 2) if linha["media"] is not None else None,
                minimo=linha["minimo"],
                maximo=linha["maximo"],
                soma=round(linha["soma"], 2),
                quantidade=linha["quantidade"],
            )
        )

    return RespostaAgregado(
        estacao=estacao,
        variavel=variavel,
        unidade=UNIDADES[variavel],
        intervalo=intervalo,
        dados=pontos,
    )


@app.get("/cobertura", tags=["metadados"])
def cobertura() -> list[dict]:
    """Mostra o que existe no banco: por estação e variável, o período e a contagem.

    Serve para o grupo acompanhar o que já foi carregado e para o dashboard
    saber quais combinações têm dado antes de montar um gráfico vazio.
    """
    etapas = [
        {
            "$group": {
                "_id": {"estacao": "$estacao", "variavel": "$variavel"},
                "primeiro": {"$min": "$timestamp"},
                "ultimo": {"$max": "$timestamp"},
                "registros": {"$sum": 1},
                "nulos": {
                    "$sum": {"$cond": [{"$eq": ["$valor", None]}, 1, 0]}
                },
            }
        },
        {"$sort": {"_id.estacao": 1, "_id.variavel": 1}},
    ]

    return [
        {
            "estacao": linha["_id"]["estacao"],
            "variavel": linha["_id"]["variavel"],
            "primeiro": para_fuso_projeto(linha["primeiro"]).isoformat(),
            "ultimo": para_fuso_projeto(linha["ultimo"]).isoformat(),
            "registros": linha["registros"],
            "nulos": linha["nulos"],
        }
        for linha in medicoes.aggregate(etapas)
    ]
