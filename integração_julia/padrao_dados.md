# Padrão de Dados do Projeto

## Objetivo

Definir uma estrutura comum para os dados meteorológicos coletados das
diferentes fontes utilizadas no projeto.

## Estrutura dos dados

Após a etapa de padronização, os registros deverão seguir uma estrutura
comum, independentemente da fonte de origem.

| Campo | Descrição |
|---|---|
| `estacao` | Identificação da estação meteorológica |
| `timestamp` | Data e hora da medição |
| `variavel` | Variável meteorológica medida |
| `valor` | Valor da medição |
| `unidade` | Unidade da medição |
| `fonte` | Origem do dado |
| `tipo_dado` | Indica se o dado é medido ou tratado |

## Variáveis e unidades

| Variável | Unidade |
|---|---|
| `irradiancia` | W/m² |
| `temperatura` | °C |
| `precipitacao` | mm |
| `umidade_relativa` | % |
| `velocidade_vento` | m/s |
| `direcao_vento` | ° |

As variáveis efetivamente utilizadas no projeto dependerão dos dados
disponíveis em cada fonte.

## Data e hora

O campo `timestamp` será utilizado para identificar o momento da medição.

Formato definido:

`YYYY-MM-DDTHH:MM:SS-03:00`

Exemplo:

`2026-10-04T14:00:00-03:00`

## Fonte dos dados

O campo `fonte` deverá identificar a origem do dado, permitindo manter a
rastreabilidade das informações.

Exemplos:

- `GAIC`
- `Open-Meteo`
- `Weather Underground`

## Tipo do dado

O campo `tipo_dado` deverá indicar se o valor corresponde a uma medição
original ou se passou por algum tratamento.

Exemplos:

- `medido`
- `tratado`
- `estimado`

Valores estimados ou tratados não devem ser confundidos com medições
originais.

## Observações

A frequência de coleta e o intervalo de reamostragem serão definidos após
a análise das características de cada fonte de dados.

As conversões de unidades e demais tratamentos necessários serão realizados
durante a etapa de ETL.