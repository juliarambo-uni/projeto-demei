"""
Tratamento dos dados da estação do GAIC (UNIJUI - SEDE).

Recebe a tabela no formato do arquivo exportado (colunas "Line#", "Date" e uma
coluna por sensor, com nomes longos) e devolve registros limpos.

Uso:
    from gaic_tratamento import tratar_tabela, ultima_leitura
    registros = tratar_tabela(df)     # lista de dicts, uma por leitura (5 em 5 min)
    atual = ultima_leitura(df)        # só a leitura mais recente
"""

import re

import pandas as pd

FUSO_LOCAL = "America/Sao_Paulo"  # Ijuí/RS (UTC-3)
FORMATO_DATA = "%d/%m/%y %H:%M:%S %z"  # ex.: 05/10/26 22:45:00 +0000

# prefixo do nome da coluna -> nome limpo no resultado
# (a ordem importa: os "-Avg" vêm antes para não casar com o prefixo curto)
MAPA_SENSORES = [
    (r"^Solar Radiation-Avg", "radiacao_solar_media_wm2"),
    (r"^Solar Radiation",     "radiacao_solar_wm2"),
    (r"^Air Temperature-Avg", "temperatura_media_c"),
    (r"^Air Temperature",     "temperatura_c"),
    (r"^Battery",             "bateria_v"),
]


def _renomear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    novos = {}
    for coluna in df.columns:
        nome = str(coluna).strip()
        if nome == "Date":
            novos[coluna] = "data_hora_utc"
            continue
        for padrao, limpo in MAPA_SENSORES:
            if re.match(padrao, nome):
                novos[coluna] = limpo
                break
    # descarta o que não foi mapeado (ex.: "Line#")
    return df[list(novos)].rename(columns=novos)


def tratar_tabela(df: pd.DataFrame) -> list[dict]:
    """Normaliza a tabela e devolve uma lista de dicts ordenada por horário."""
    limpo = _renomear_colunas(df)

    limpo["data_hora_utc"] = pd.to_datetime(
        limpo["data_hora_utc"], format=FORMATO_DATA, utc=True
    )
    limpo.insert(
        1, "data_hora_local", limpo["data_hora_utc"].dt.tz_convert(FUSO_LOCAL)
    )

    limpo = (
        limpo.drop_duplicates(subset="data_hora_utc")
        .sort_values("data_hora_utc")
        .reset_index(drop=True)
    )

    # valores não numéricos viram NaN; NaN vira None no resultado
    sensores = [c for c in limpo.columns if not c.startswith("data_hora")]
    limpo[sensores] = limpo[sensores].apply(pd.to_numeric, errors="coerce")

    limpo["data_hora_utc"] = limpo["data_hora_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    limpo["data_hora_local"] = limpo["data_hora_local"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    limpo = limpo.astype(object).where(limpo.notna(), None)
    return limpo.to_dict(orient="records")


def ultima_leitura(df: pd.DataFrame) -> dict:
    """Só a leitura mais recente."""
    registros = tratar_tabela(df)
    if not registros:
        raise ValueError("Nenhuma leitura encontrada.")
    return registros[-1]


# ======================================================================
# Tratamento da resposta da API (GET /v1/data da LI-COR Cloud)
# ======================================================================
# Cada item de data[] é UMA leitura de UM sensor:
#   {"logger_sn", "sensor_sn", "timestamp", "data_type", "value", "unit",
#    "sensor_measurement_type"}
# Aqui juntamos tudo por horário, uma linha por horário, como na planilha.

_SUFIXO_TIPO = {
    "CURRENT": "",
    "AVERAGE": "_media",
    "MINIMUM": "_min",
    "MAXIMUM": "_max",
    "STANDARD_DEVIATION": "_desvio",
}


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(texto).lower()).strip("_")


def _nome_base(tipo_medida: str) -> str:
    t = str(tipo_medida).lower()
    if "solar" in t:
        return "radiacao_solar"
    if "temp" in t:
        return "temperatura"
    if "batter" in t:
        return "bateria"
    return _slug(t)  # qualquer sensor novo aparece com o próprio nome


def tratar_resposta_api(resposta: dict) -> dict:
    """
    Recebe o JSON da API e devolve:
      {"unidades": {campo: unidade}, "leituras": [ {...uma por horário...} ]}
    """
    itens = (resposta or {}).get("data") or []
    if not itens:
        return {"unidades": {}, "leituras": []}

    df = pd.DataFrame(itens)

    # nome do campo = tipo de medida + tipo do dado (instantâneo, média...)
    df["campo"] = [
        _nome_base(m) + _SUFIXO_TIPO.get(d, "_" + _slug(d))
        for m, d in zip(df["sensor_measurement_type"], df["data_type"])
    ]

    # se dois sensores diferentes gerarem o mesmo nome, separa pelo serial
    n_sensores = df.groupby("campo")["sensor_sn"].transform("nunique")
    df.loc[n_sensores > 1, "campo"] = (
        df["campo"] + "_" + df["sensor_sn"].map(_slug)
    )

    df["data_hora"] = pd.to_datetime(df["timestamp"], utc=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    unidades = df.drop_duplicates("campo").set_index("campo")["unit"].to_dict()

    largo = (
        df.pivot_table(index="data_hora", columns="campo", values="value", aggfunc="last")
        .sort_index()
    )
    largo.insert(0, "data_hora_local", largo.index.tz_convert(FUSO_LOCAL))
    largo.insert(0, "data_hora_utc", largo.index)
    largo = largo.reset_index(drop=True)

    largo["data_hora_utc"] = largo["data_hora_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    largo["data_hora_local"] = largo["data_hora_local"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    largo = largo.astype(object).where(largo.notna(), None)

    return {"unidades": unidades, "leituras": largo.to_dict(orient="records")}
