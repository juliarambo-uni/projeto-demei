"""
coleta_open_meteo.py
--------------------
Coletor de dados meteorológicos da API Open-Meteo (https://open-meteo.com).

Este arquivo tem DUAS formas de uso:

1) COMO FUNÇÃO (o sistema/ETL vai importar e chamar):
       from coleta_open_meteo import coletar_open_meteo
       pacote = coletar_open_meteo("2026-09-01", "2026-09-07")

2) COMO SCRIPT (para testar na mão pelo terminal):
       python coleta_open_meteo.py --inicio 2026-09-01 --fim 2026-09-07

Regra de ouro desta etapa: NÃO transformar nada. Os dados brutos são salvos
exatamente como a API devolveu; quem padroniza é a etapa seguinte (ETL).
"""

import argparse
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# --------------------------------------------------------------------------
# CONFIGURAÇÕES (constantes no topo = fácil de achar e alterar)
# --------------------------------------------------------------------------
VERSAO_COLETOR = "1.0.0"

# Dois "endereços" da Open-Meteo:
URL_HISTORICO = "https://archive-api.open-meteo.com/v1/archive"  # dados passados
URL_PREVISAO = "https://api.open-meteo.com/v1/forecast"          # recente/futuro

# Ponto padrão: Ijuí - RS (região do DEMEI). Pode ser trocado ao chamar a função.
ESTACAO_ID_PADRAO = "OPENMETEO_IJUI"
LATITUDE_PADRAO = -28.388
LONGITUDE_PADRAO = -53.914

# Variáveis horárias pedidas (as relevantes para geração fotovoltaica).
VARIAVEIS_PADRAO = [
    "temperature_2m",            # temperatura a 2 m
    "relative_humidity_2m",      # umidade relativa
    "pressure_msl",              # pressão ao nível do mar
    "surface_pressure",          # pressão na superfície
    "precipitation",             # precipitação
    "cloud_cover",               # nebulosidade (%)
    "wind_speed_10m",            # velocidade do vento a 10 m
    "wind_direction_10m",        # direção do vento a 10 m
    "shortwave_radiation",       # irradiância global horizontal (GHI)
    "direct_radiation",          # irradiância direta (horizontal)
    "diffuse_radiation",         # irradiância difusa
    "direct_normal_irradiance",  # irradiância direta normal (DNI)
]

# Pasta onde os brutos ficam guardados temporariamente.
PASTA_BRUTOS_PADRAO = Path("data/raw/open_meteo")

# Quantos dias coletar por padrão quando rodado como script (30 = ~1 mês).
DIAS_PADRAO = 30

# Unidades pedidas EXPLICITAMENTE (não dependemos do padrão da API).
# Padrão SI/métrico: facilita a padronização com as outras fontes.
UNIDADES = {
    "temperature_unit": "celsius",   # °C
    "wind_speed_unit": "ms",         # m/s  (o padrão da API seria km/h)
    "precipitation_unit": "mm",      # mm
}

TIMEOUT_SEGUNDOS = 30
MAX_TENTATIVAS = 3

logger = logging.getLogger("coleta.open_meteo")


class ColetaOpenMeteoError(Exception):
    """Erro específico desta coleta (quem chamar a função captura este tipo)."""


# --------------------------------------------------------------------------
# FUNÇÕES AUXILIARES (uso interno, por isso o "_" no começo do nome)
# --------------------------------------------------------------------------
def _para_data(valor):
    """Aceita 'AAAA-MM-DD' (texto) ou objeto date e devolve sempre um date."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except ValueError as erro:
        raise ColetaOpenMeteoError(
            f"Data inválida: {valor!r}. Use o formato AAAA-MM-DD."
        ) from erro


def _requisitar_com_tentativas(url, parametros):
    """Faz o GET na API. Se der erro de rede/servidor, tenta de novo (até 3x)."""
    ultimo_erro = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resposta = requests.get(url, params=parametros, timeout=TIMEOUT_SEGUNDOS)

            # 400 = pedido inválido (erro nosso): não adianta tentar de novo.
            if resposta.status_code == 400:
                motivo = resposta.json().get("reason", resposta.text)
                raise ColetaOpenMeteoError(f"Open-Meteo recusou o pedido: {motivo}")

            resposta.raise_for_status()  # levanta erro p/ 429, 500, 503...
            return resposta

        except ColetaOpenMeteoError:
            raise
        except (requests.RequestException, ValueError) as erro:
            ultimo_erro = erro
            logger.warning("Tentativa %d/%d falhou: %s", tentativa, MAX_TENTATIVAS, erro)
            if tentativa < MAX_TENTATIVAS:
                time.sleep(2 ** tentativa)  # espera 2s, depois 4s...

    raise ColetaOpenMeteoError(
        f"Falha após {MAX_TENTATIVAS} tentativas: {ultimo_erro}"
    )


def salvar_bruto(pacote, pasta_saida=PASTA_BRUTOS_PADRAO):
    """Salva o pacote (metadados + dados brutos) em um arquivo JSON e devolve o caminho."""
    pasta = Path(pasta_saida)
    pasta.mkdir(parents=True, exist_ok=True)

    meta = pacote["metadados"]
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    nome = (
        f"open_meteo_{meta['estacao_id']}_"
        f"{meta['periodo']['inicio']}_{meta['periodo']['fim']}_{carimbo}.json"
    )
    caminho = pasta / nome

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(pacote, arquivo, ensure_ascii=False, indent=2)

    logger.info("Bruto salvo em %s", caminho)
    return caminho


def limpar_brutos_antigos(dias=7, pasta=PASTA_BRUTOS_PADRAO):
    """Apaga brutos com mais de N dias (é o lado 'temporário' dos dados brutos)."""
    pasta = Path(pasta)
    if not pasta.exists():
        return 0
    limite = time.time() - dias * 86400
    apagados = 0
    for arquivo in pasta.glob("open_meteo_*.json"):
        if arquivo.stat().st_mtime < limite:
            arquivo.unlink()
            apagados += 1
    return apagados


# --------------------------------------------------------------------------
# FUNÇÃO PRINCIPAL (a que o sistema vai chamar)
# --------------------------------------------------------------------------
def coletar_open_meteo(
    data_inicio,
    data_fim,
    latitude=LATITUDE_PADRAO,
    longitude=LONGITUDE_PADRAO,
    variaveis=None,
    estacao_id=ESTACAO_ID_PADRAO,
    modo="historico",
    salvar=True,
    pasta_saida=PASTA_BRUTOS_PADRAO,
):
    """
    Coleta dados horários da Open-Meteo para um ponto e um período.

    Parâmetros
    ----------
    data_inicio, data_fim : 'AAAA-MM-DD' ou date (inclusivos)
    latitude, longitude   : coordenadas do ponto (graus decimais)
    variaveis             : lista de variáveis horárias (padrão: VARIAVEIS_PADRAO)
    estacao_id            : identificador da "estação" no nosso sistema
    modo                  : 'historico' (dados passados) ou 'previsao' (recente/futuro)
    salvar                : True = grava o JSON bruto em disco
    pasta_saida           : pasta onde gravar o bruto

    Retorna
    -------
    dict com duas chaves:
      'metadados'    -> de onde veio, quando foi coletado, parâmetros usados
      'dados_brutos' -> o JSON original da API, SEM alterações

    Levanta ColetaOpenMeteoError se algo der errado.
    """
    inicio = _para_data(data_inicio)
    fim = _para_data(data_fim)
    if inicio > fim:
        raise ColetaOpenMeteoError("data_inicio não pode ser posterior a data_fim.")
    if modo not in ("historico", "previsao"):
        raise ColetaOpenMeteoError("modo deve ser 'historico' ou 'previsao'.")

    variaveis = variaveis or VARIAVEIS_PADRAO
    url = URL_HISTORICO if modo == "historico" else URL_PREVISAO

    parametros = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": inicio.isoformat(),
        "end_date": fim.isoformat(),
        "hourly": ",".join(variaveis),
        "timezone": "UTC",  # horários em UTC: evita confusão de fuso/horário de verão
        **UNIDADES,
    }

    logger.info("Coletando Open-Meteo (%s) %s -> %s", modo, inicio, fim)
    resposta = _requisitar_com_tentativas(url, parametros)
    dados = resposta.json()

    # Validação mínima: a resposta tem o que esperamos?
    if "hourly" not in dados or "time" not in dados["hourly"]:
        raise ColetaOpenMeteoError("Resposta da API sem o bloco 'hourly/time'.")

    pacote = {
        "metadados": {
            "fonte": "open-meteo",
            "modo": modo,
            "estacao_id": estacao_id,
            "url_requisitada": resposta.url,
            "parametros": parametros,
            "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
            "coletado_em_utc": datetime.now(timezone.utc).isoformat(),
            "status_http": resposta.status_code,
            "total_registros": len(dados["hourly"]["time"]),
            "versao_coletor": VERSAO_COLETOR,
            "arquivo_bruto": None,
        },
        "dados_brutos": dados,
    }

    if salvar:
        caminho = salvar_bruto(pacote, pasta_saida)
        pacote["metadados"]["arquivo_bruto"] = str(caminho)

    return pacote


# --------------------------------------------------------------------------
# MODO SCRIPT (só roda quando executamos: python coleta_open_meteo.py)
# --------------------------------------------------------------------------
def _main():
    # A API histórica tem ~5 dias de atraso; por isso o padrão termina há 6 dias.
    fim_padrao = date.today() - timedelta(days=6)

    parser = argparse.ArgumentParser(description="Coleta bruta da Open-Meteo.")
    parser.add_argument("--inicio", default=None,
                        help="AAAA-MM-DD. Se omitido, usa fim - (dias-1).")
    parser.add_argument("--fim", default=fim_padrao.isoformat())
    parser.add_argument("--dias", type=int, default=DIAS_PADRAO,
                        help=f"Tamanho da janela quando --inicio é omitido (padrão {DIAS_PADRAO}).")
    parser.add_argument("--lat", type=float, default=LATITUDE_PADRAO)
    parser.add_argument("--lon", type=float, default=LONGITUDE_PADRAO)
    parser.add_argument("--estacao-id", default=ESTACAO_ID_PADRAO)
    parser.add_argument("--modo", choices=["historico", "previsao"], default="historico")
    parser.add_argument("--pasta", default=str(PASTA_BRUTOS_PADRAO))
    parser.add_argument("--limpar-dias", type=int, default=None,
                        help="Apaga brutos com mais de N dias antes de coletar.")
    args = parser.parse_args()

    if args.inicio is None:
        args.inicio = (_para_data(args.fim) - timedelta(days=args.dias - 1)).isoformat()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.limpar_dias is not None:
        n = limpar_brutos_antigos(args.limpar_dias, args.pasta)
        logger.info("%d arquivo(s) antigo(s) removido(s).", n)

    try:
        pacote = coletar_open_meteo(
            args.inicio, args.fim,
            latitude=args.lat, longitude=args.lon,
            estacao_id=args.estacao_id, modo=args.modo,
            pasta_saida=args.pasta,
        )
    except ColetaOpenMeteoError as erro:
        logger.error("Coleta falhou: %s", erro)
        raise SystemExit(1)

    meta = pacote["metadados"]
    print(f"OK: {meta['total_registros']} registros horários coletados.")
    print(f"Arquivo: {meta['arquivo_bruto']}")


if __name__ == "__main__":
    _main()
