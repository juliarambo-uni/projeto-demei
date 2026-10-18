
import json #usado para conseguir ler o json
import re  #usado para buscar, filtrar, validar, extrair ou substituir padrões específicos dentro de textos
from datetime import datetime #conversão e manipulação de fusos horários
from pathlib import Path #para navegar por pastas e localizar os arquivos no sistema de arquivos
from zoneinfo import ZoneInfo #conversão e manipulação de fusos horários
import pandas as pd #panda cria estruturas 'DataFrames' (tabelas tipo excel) para poder ler grandes volumes de dados

# Unidades de medida
UNIDADES = {
    "irradiancia": "W/m²",
    "temperatura": "°C",
    "precipitacao": "mm",
    "umidade_relativa": "%",
    "velocidade_vento": "m/s",
    "direcao_vento": "°",
}

pasta_raiz = Path("") #Caminho das pastas, não definido

pasta_entrada = pasta_raiz / "dados_brutos" #pasta que será buscado os json
pasta_brutos = pasta_raiz / "dados_brutos_lidos" #pasta onde ficarão os arquivos .json brutos depois do etl (para o código ler apenas arquivos novos)
pasta_saida = pasta_raiz / "dados_padronizados" #pasta onde os arquivos padronizados vão ficar gravados

pasta_saida.mkdir(parents=True, exist_ok=True) #cria a pasta do json caso ela ainda não exista
pasta_brutos.mkdir(parents=True, exist_ok=True) #cria a pasta do json bruto caso ela ainda não exista

ficheiro_saida = pasta_saida / "medicoes_padronizadas.json" #caminho do json e seu nome

arquivos_json = list(pasta_entrada.glob("*.json")) #busca todos os .json da pasta de dados_brutos
lista_dataframes_longos = []
arquivos_para_mover = []

for caminho_arquivo in arquivos_json: #percorre todos os arquivos .json encontrados
    with open(caminho_arquivo, "r", encoding="utf-8") as arquivo: #abre o arquivo em modo leitura, padrçao utf-8
        dados = json.load(arquivo) #coloca o arquivo json em memória python

    nome_arquivo = caminho_arquivo.name.lower() #deixa o nome do arquivo em minúsculo
    df_temp = pd.DataFrame() #começa um DataFrame zerado

    # --- Weather Underground ---
    if "weather_underground" in nome_arquivo or (
        isinstance(dados, list) and len(dados) > 0 and "Dew Point" in dados[0] #verifica se o weather_underground existe no nome do arquivo ou se posuui a chave DewPoint
    ):
        df_raw = pd.DataFrame(dados)

        df_temp["timestamp"] = (
            pd.to_datetime(
                df_raw["Date"].astype(str) + " " + df_raw["Time"].astype(str),
                format="%Y-%m-%d %I:%M %p",
                errors="coerce"
            )
            .dt.tz_localize(ZoneInfo("America/Sao_Paulo"))
            .dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        )

        df_temp["temperatura"] = (
            df_raw["Temperature"].astype(str).str.extract(r"(-?\d+\.?\d*)")[0].astype(float) #tira a informação da unidade de medida do valor
        )
        df_temp["umidade_relativa"] = (
            df_raw["Humidity"].astype(str).str.extract(r"(\d+\.?\d*)")[0].astype(float)
        )
        df_temp["precipitacao"] = (
            df_raw["Precip. Accum."].astype(str).str.extract(r"(\d+\.?\d*)")[0].astype(float)
        )
        # Conversão de velocidade do vento (km/h para m/s)
        df_temp["velocidade_vento"] = (
            df_raw["Speed"].astype(str).str.extract(r"(\d+\.?\d*)")[0].astype(float) / 3.6
        )
        df_temp["irradiancia"] = (
            df_raw["Solar"].astype(str).str.extract(r"(\d+\.?\d*)")[0].astype(float)
        )

        df_temp["estacao"] = "wu_floresta"
        df_temp["fonte"] = "Weather Underground"
        df_temp["tipo_dado"] = "medido"

    # --- Open-Meteo ---
    elif "open_meteo" in nome_arquivo or (
        isinstance(dados, dict) and "dados_brutos" in dados #verifica no nome do arquivo
    ):
        hourly_data = dados["dados_brutos"]["hourly"] #pega o array da dados horários
        df_raw = pd.DataFrame(hourly_data)

        df_temp["timestamp"] = (
            pd.to_datetime(df_raw["time"])
            .dt.tz_localize("UTC")
            .dt.tz_convert(ZoneInfo("America/Sao_Paulo"))
            .dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        ) #recebe o horário em UTC, ajusta para America/Sao_Paulo e gera no formato ISO 8601
        df_temp["temperatura"] = df_raw["temperature_2m"].astype(float)
        df_temp["umidade_relativa"] = df_raw["relative_humidity_2m"].astype(float)
        df_temp["precipitacao"] = df_raw["precipitation"].astype(float)
        df_temp["velocidade_vento"] = df_raw["wind_speed_10m"].astype(float)
        df_temp["irradiancia"] = df_raw["shortwave_radiation"].astype(float)

        df_temp["estacao"] = "om_ijui"
        df_temp["fonte"] = "Open-Meteo"
        df_temp["tipo_dado"] = "medido"

    # --- GAIC ---
    # --- GAIC ---
    elif "gaic" in nome_arquivo or isinstance(dados, (dict, list)):
        # Extrai o array interno de 'leituras' caso seja o formato aninhado do GAIC
        if isinstance(dados, dict) and "leituras" in dados:
            df_raw = pd.DataFrame(dados["leituras"])
        else:
            df_raw = pd.DataFrame([dados] if isinstance(dados, dict) else dados)

        # 1. Busca dinâmica da coluna de data/hora
        col_tempo = next(
            (col for col in ["data_hora_local", "data_hora_utc", "timestamp", "data_hora", "time", "data", "Time"] if col in df_raw.columns), 
            None
        )
        
        if col_tempo:
            df_temp["timestamp"] = pd.to_datetime(df_raw[col_tempo]).dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        else:
            df_temp["timestamp"] = pd.Timestamp.now(tz=ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%dT%H:%M:%S%z")

        # 2. Mapeamento seguro de colunas existentes no GAIC
        for col_origem, col_destino in [
            ("temperatura", "temperatura"),
            ("temperatura_media", "temperatura"),
            ("umidade", "umidade_relativa"),
            ("umidade_relativa", "umidade_relativa"),
            ("precipitacao", "precipitacao"),
            ("vento", "velocidade_vento"),
            ("velocidade_vento", "velocidade_vento"),
            ("radiacao_solar", "irradiancia"),
            ("radiacao_solar_media", "irradiancia"),
            ("radiacao", "irradiancia"),
            ("irradiancia", "irradiancia")
        ]:
            if col_origem in df_raw.columns and col_destino not in df_temp.columns:
                df_temp[col_destino] = pd.to_numeric(df_raw[col_origem], errors="coerce")

        # 3. Metadados totalmente fixos
        df_temp["estacao"] = "gaic_centro"
        df_temp["fonte"] = "GAIC"
        df_temp["tipo_dado"] = "medido"

    if not df_temp.empty:
        #separam as colunas de medição com as dos dados
        cols_id = ["estacao", "timestamp", "fonte", "tipo_dado"]
        cols_vars = [c for c in df_temp.columns if c not in cols_id]

        #transforma colunas de variáveis em linhas com pares de variável e valor
        df_melted = df_temp.melt(
            id_vars=cols_id,
            value_vars=cols_vars,
            var_name="variavel",
            value_name="valor"
        )

        df_melted["valor"] = df_melted["valor"].where(pd.notna(df_melted["valor"]), None) # Substitui os NaN/NaT do Pandas por None (que vira null no JSON final)
        df_melted["unidade"] = df_melted["variavel"].map(UNIDADES) #cria coluna de unidade, associada ao dicionário UNIDADES

        df_melted = df_melted[[
            "estacao", "timestamp", "variavel", "valor", "unidade", "fonte", "tipo_dado"
        ]] #reordena as colunas

        lista_dataframes_longos.append(df_melted) #guarda a tabela na lista
        arquivos_para_mover.append(caminho_arquivo) #salva o arquivo para que seja movido

# 5. Consolidação e Gravação do Arquivo Final
if lista_dataframes_longos:
    df_padronizado = pd.concat(lista_dataframes_longos, ignore_index=True) #junta todas as tabelas dos json em um unico Data Frame
    df_padronizado = df_padronizado.sort_values(by=["timestamp", "estacao", "variavel"]).reset_index(drop=True) #ordena a lista por data e horário

    #pega a menor e a maior data 
    data_inicio = df_padronizado["timestamp"].min()[:10] #(o 10 é até onde vai a data)
    data_fim = df_padronizado["timestamp"].max()[:10]

    horario = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%H%M")

    if data_inicio == data_fim:
        nome_ficheiro_saida = f"medicoes_padronizadas_{data_inicio}_{horario}.json"
    else:
        nome_ficheiro_saida = f"medicoes_padronizadas_{data_inicio}_{data_fim}_{horario}.json"

    ficheiro_saida = pasta_saida / nome_ficheiro_saida

    registros = df_padronizado.to_dict(orient="records") #converte de tabela Pandas para uma lista de dicionários do python

    with open(ficheiro_saida, "w", encoding="utf-8") as f: #cria o arquivo
        json.dump(registros, f, ensure_ascii=False, indent=2)

    # Move os arquivos lidos para a pasta 'dados_brutos_lidos'
    for arquivo in arquivos_para_mover:
        destino = pasta_brutos / arquivo.name
        arquivo.rename(destino)

    print(f"Sucesso! {len(arquivos_json)} arquivo(s) processado(s).")
    print(f"O arquivo padronizado foi salvo em:\n{ficheiro_saida}")
else:
    print(f"Nenhum arquivo .json para processar na pasta:\n{pasta_entrada}")
