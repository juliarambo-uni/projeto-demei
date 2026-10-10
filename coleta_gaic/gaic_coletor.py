"""
Coletor de dados da estação meteorológica do GAIC (Unijuí).

Três partes:
  1. coletar_dados_brutos()  -> faz a requisição à API
  2. salvar_bruto()          -> guarda o JSON bruto temporariamente em disco
  3. obter_dados_gaic()      -> função que o sistema vai chamar

Configuração por variáveis de ambiente (não deixe o token no código):
  GAIC_TOKEN        token gerado em LI-COR Cloud > Data > API (obrigatório)
  GAIC_LOGGER_SN    número de série da estação (obrigatório; vários: separe por vírgula)
  GAIC_API_URL      padrão: https://api.licor.cloud/v1/data
  GAIC_RAW_DIR      pasta dos dados brutos (padrão: ./dados_brutos)
  GAIC_RAW_TTL_H    horas até apagar brutos antigos (padrão: 24)

API: LI-COR Cloud (antigo HOBOlink), GET /v1/data, autenticação Bearer.
Parâmetros obrigatórios: loggers, start_date_time, end_date_time
(formato yyyy-MM-dd HH:mm:ss, sempre em UTC).

Dependência: pip install requests
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

TIMEOUT = 30  # segundos


# ---------------------------------------------------------------- config
def _config() -> dict:
    token = os.environ.get("GAIC_TOKEN")
    logger_sn = os.environ.get("GAIC_LOGGER_SN")
    if not token or not logger_sn:
        raise RuntimeError("Defina as variáveis GAIC_TOKEN e GAIC_LOGGER_SN.")
    return {
        "token": token,
        "logger_sn": logger_sn,
        "url": os.environ.get("GAIC_API_URL", "https://api.licor.cloud/v1/data"),
        "raw_dir": Path(os.environ.get("GAIC_RAW_DIR", "dados_brutos")),
        "ttl_h": float(os.environ.get("GAIC_RAW_TTL_H", "24")),
    }


# ------------------------------------------------------------ 1. coleta
def coletar_dados_brutos(horas: float = 24) -> dict:
    """Pede à API as leituras das últimas `horas` horas (janela em UTC)."""
    cfg = _config()
    fim = datetime.now(timezone.utc)
    inicio = fim - timedelta(hours=horas)
    fmt = "%Y-%m-%d %H:%M:%S"

    resp = requests.get(
        cfg["url"],
        headers={"Authorization": f"Bearer {cfg['token']}"},
        params={
            "loggers": cfg["logger_sn"],
            "start_date_time": inicio.strftime(fmt),
            "end_date_time": fim.strftime(fmt),
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()  # 401/403 = token inválido; 429 = limite de requisições
    dados = resp.json()

    # a API sinaliza truncamento no corpo da resposta: reduza a janela
    if isinstance(dados, dict) and dados.get("max_results"):
        print("AVISO: resultado truncado pela API. Use uma janela de tempo menor.")
    return dados


# ------------------------------------------- 2. armazenamento temporário
def salvar_bruto(dados: dict | list) -> Path:
    """Salva o JSON bruto com timestamp e apaga arquivos mais antigos que o TTL."""
    cfg = _config()
    pasta: Path = cfg["raw_dir"]
    pasta.mkdir(parents=True, exist_ok=True)

    arquivo = pasta / f"gaic_{datetime.now():%Y%m%d_%H%M%S}.json"
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    limite = time.time() - cfg["ttl_h"] * 3600
    for antigo in pasta.glob("gaic_*.json"):
        if antigo.stat().st_mtime < limite:
            antigo.unlink()

    return arquivo


# ------------------------------------------ 3. função para o sistema
def obter_dados_gaic(horas: float = 24, salvar: bool = True, tratar: bool = True):
    """
    Função de entrada para o sistema.
    Coleta as últimas `horas` horas e guarda o JSON bruto (temporário).
    Com tratar=True devolve {"unidades": ..., "leituras": [...]}, uma leitura
    por horário; com tratar=False devolve o JSON bruto da API.
    """
    bruto = coletar_dados_brutos(horas)
    if salvar:
        salvar_bruto(bruto)
    if not tratar:
        return bruto

    from gaic_tratamento import tratar_resposta_api  # mesma pasta

    return tratar_resposta_api(bruto)


if __name__ == "__main__":
    resultado = obter_dados_gaic()
    print("Unidades:", resultado["unidades"])
    print("Total de leituras:", len(resultado["leituras"]))
    if resultado["leituras"]:
        print("Mais recente:")
        print(json.dumps(resultado["leituras"][-1], ensure_ascii=False, indent=2))
