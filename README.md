# Projeto Integrador — Gestão da Infraestrutura

Projeto desenvolvido para a construção de uma infraestrutura de dados meteorológicos
voltada ao apoio do planejamento e da operação de geração fotovoltaica do DEMEI.

## Equipe e responsabilidades

| Responsável | Área |
|---|---|
| Júlia | Integração e organização do projeto |
| Vanessa | Coleta de dados do GAIC/Unijuí |
| Murilo | Coleta de dados do Open-Meteo |
| Carol | Coleta de dados do Weather Underground |
| Poli | ETL e processamento dos dados |
| Matheus | Banco de dados e API |
| Diovana | Dashboard e visualização |

## Estrutura do projeto

- `integração_julia` — integração e organização geral do projeto
- `coleta_dados` — coleta das diferentes fontes de dados
  - `gaic_vanessa` — dados do GAIC/Unijuí
  - `open_meteo_murilo` — dados do Open-Meteo
  - `weather_underground_carol` — dados do Weather Underground
- `processamento_etl_poli` — tratamento e padronização dos dados
- `BD_api_matheus` — banco de dados e API
- `dashboard_diovana` — dashboard e visualização
- `testes` — testes do projeto

## Fluxo da solução

Fontes de dados → Coleta → Padronização/ETL → Armazenamento → API → Dashboard