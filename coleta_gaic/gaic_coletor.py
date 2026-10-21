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
  GAIC_JANELA_H     tamanho de cada pedido à API em períodos longos (padrão: 168 = 7 dias)

API: LI-COR Cloud (antigo HOBOlink), GET /v1/data, autenticação Bearer.
Parâmetros obrigatórios: loggers, start_date_time, end_date_time
(formato yyyy-MM-dd HH:mm:ss, sempre em UTC).

Períodos longos (ex.: um ano = 8760 horas): o script divide o pedido em janelas
menores, espera entre elas e, se a API cortar uma janela (max_results), divide
de novo ao meio até caber. Atalho: obter_dados_gaic_anual().

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
        "janela_h": float(os.environ.get("GAIC_JANELA_H", "168")),
    }


# ------------------------------------------------------------ 1. coleta
FMT = "%Y-%m-%d %H:%M:%S"
PAUSA_ENTRE_PEDIDOS = 0.5   # segundos, para não estourar o limite da API
TENTATIVAS_429 = 4          # quantas vezes tentar de novo se a API mandar esperar
JANELA_MINIMA_H = 1         # não divide janelas menores que isso


def _pedir(cfg: dict, inicio: datetime, fim: datetime) -> dict:
    """Um pedido à API para o intervalo [inicio, fim] (UTC)."""
    for tentativa in range(TENTATIVAS_429):
        resp = requests.get(
            cfg["url"],
            headers={"Authorization": f"Bearer {cfg['token']}"},
            params={
                "loggers": cfg["logger_sn"],
                "start_date_time": inicio.strftime(FMT),
                "end_date_time": fim.strftime(FMT),
            },
            timeout=TIMEOUT,
        )
        if resp.status_code == 429 and tentativa < TENTATIVAS_429 - 1:
            espera = float(resp.headers.get("Retry-After", 30))
            print(f"API pediu para esperar {espera:.0f}s (429). Tentando de novo...")
            time.sleep(espera)
            continue
        if resp.status_code >= 400:
            # a API costuma explicar o motivo no corpo da resposta
            print(f"ERRO {resp.status_code} da API: {resp.text[:500]}")
        resp.raise_for_status()  # 401/403 = token inválido
        return resp.json()
    raise RuntimeError("Não foi possível obter dados (limite de requisições).")


def _coletar_janela(cfg: dict, inicio: datetime, fim: datetime) -> list:
    """Coleta uma janela; se a API cortar o resultado, divide ao meio e junta."""
    dados = _pedir(cfg, inicio, fim)
    itens = dados.get("data") or []
    cortou = bool(dados.get("max_results"))

    if cortou and (fim - inicio) > timedelta(hours=JANELA_MINIMA_H):
        meio = inicio + (fim - inicio) / 2
        time.sleep(PAUSA_ENTRE_PEDIDOS)
        return (_coletar_janela(cfg, inicio, meio)
                + _coletar_janela(cfg, meio, fim))
    if cortou:
        print(f"AVISO: janela {inicio} a {fim} ainda truncada pela API.")
    return itens


def coletar_dados_brutos(horas: float = 24) -> dict:
    """
    Pede à API as leituras das últimas `horas` horas (janela em UTC).
    Períodos longos são divididos em janelas (GAIC_JANELA_H, padrão 7 dias).
    """
    cfg = _config()
    fim = datetime.now(timezone.utc).replace(microsecond=0)
    inicio = fim - timedelta(hours=horas)
    passo = timedelta(hours=cfg["janela_h"])

    janelas = []
    atual = inicio
    while atual < fim:
        janelas.append((atual, min(atual + passo, fim)))
        atual += passo

    itens = []
    for i, (ini, fi) in enumerate(janelas, start=1):
        if len(janelas) > 1:
            print(f"Janela {i}/{len(janelas)}: {ini:%Y-%m-%d} a {fi:%Y-%m-%d}")
        itens += _coletar_janela(cfg, ini, fi)
        if i < len(janelas):
            time.sleep(PAUSA_ENTRE_PEDIDOS)

    return {"data": itens, "max_results": False, "janelas": len(janelas)}


# ------------------------------------------- 2. armazenamento temporário
def salvar_bruto(dados: dict | list) -> Path:
    """Salva o JSON bruto com timestamp e apaga arquivos mais antigos que o TTL."""
    cfg = _config()
    pasta: Path = cfg["raw_dir"]
    pasta.mkdir(parents=True, exist_ok=True)

    arquivo = pasta / f"gaic_{datetime.now():%Y%m%d_%H%M%S}.json"
    grande = isinstance(dados, dict) and len(dados.get("data") or []) > 5000
    arquivo.write_text(
        json.dumps(dados, ensure_ascii=False, indent=None if grande else 2),
        encoding="utf-8",
    )

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


def obter_dados_gaic_anual(salvar: bool = True, tratar: bool = True):
    """Atalho: coleta os últimos 365 dias (8760 horas)."""
    return obter_dados_gaic(horas=24 * 365, salvar=salvar, tratar=tratar)


if __name__ == "__main__":
    resultado = obter_dados_gaic()
    print("Unidades:", resultado["unidades"])
    print("Total de leituras:", len(resultado["leituras"]))
    if resultado["leituras"]:
        print("Mais recente:")
        print(json.dumps(resultado["leituras"][-1], ensure_ascii=False, indent=2))
