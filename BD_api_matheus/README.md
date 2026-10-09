# Banco de Dados e API

Responsável: Matheus

Esta etapa recebe os dados já padronizados pelo ETL, armazena no MongoDB e
disponibiliza para o dashboard e outros sistemas através de uma API.

## Como rodar

Requer Python 3.11 ou mais novo. Testado no 3.14.

### Windows (Prompt de Comando)

```bat
cd BD_api_matheus

python -m pip install -r requirements.txt

copy .env.example .env
notepad .env

python scripts\criar_indices.py
python scripts\gerar_dados_teste.py --dias 30
python -m uvicorn api.main:app --reload
```

### Linux e Mac

```bash
cd BD_api_matheus

pip install -r requirements.txt

cp .env.example .env

python scripts/criar_indices.py
python scripts/gerar_dados_teste.py --dias 30
uvicorn api.main:app --reload
```

Documentação interativa: http://localhost:8000/docs

## Estrutura do banco

### Collection `medicoes`

Um documento por medição, seguindo `integração_julia/padrao_dados.md`:

```json
{
  "estacao": "gaic_centro",
  "timestamp": "2026-10-06T14:00:00Z",
  "variavel": "irradiancia",
  "valor": 842.3,
  "unidade": "W/m²",
  "fonte": "GAIC",
  "tipo_dado": "medido"
}
```

Quando a medição falhou, `valor` vem como `null`. O registro existe assim
mesmo, para o dashboard conseguir mostrar a lacuna no gráfico.

### Collection `estacoes`

Dados cadastrais de cada estação. É daqui que sai o mapa do dashboard.

```json
{
  "estacao": "gaic_centro",
  "nome": "Centro",
  "latitude": -28.3880,
  "longitude": -53.9140,
  "altitude": 348.0,
  "fonte": "GAIC",
  "variaveis": ["irradiancia", "temperatura", "umidade_relativa"],
  "ativa": true
}
```

O campo `estacao` é um código fixo que nunca muda. O campo `nome` é só para
exibição e pode mudar sem quebrar nada.

### Índices

| Índice | Campos | Para quê |
|---|---|---|
| `idx_unico_medicao` | estacao, timestamp, variavel, fonte | Impede duplicata se o ETL rodar duas vezes |
| `idx_consulta` | estacao, variavel, timestamp | É o que a API usa nas consultas |
| `idx_timestamp` | timestamp | Consultas por período sem filtrar estação |

### Fuso horário

O MongoDB guarda datas em UTC internamente. A regra do projeto é:

- ao gravar: converte de UTC-3 para UTC;
- ao ler: converte de volta para UTC-3.

A API sempre devolve no formato `YYYY-MM-DDTHH:MM:SS-03:00`, como definido no
padrão do projeto.

## Endpoints

| Método | Rota | O que faz |
|---|---|---|
| GET | `/saude` | Diz se a API e o banco estão no ar |
| GET | `/variaveis` | Lista as variáveis e suas unidades |
| GET | `/estacoes` | Lista as estações com latitude e longitude |
| GET | `/estacoes/{codigo}` | Busca uma estação |
| GET | `/medicoes` | Dados brutos, com filtro e paginação |
| GET | `/medicoes/ultima` | Medição mais recente (painel de tempo real) |
| GET | `/medicoes/agregado` | Média/mín/máx por hora, dia ou mês |
| GET | `/cobertura` | O que já existe no banco, por estação e variável |

### Exemplos

```
# Temperatura da estação Centro nos últimos dias
/medicoes?estacao=gaic_centro&variavel=temperatura&inicio=2026-10-01T00:00:00-03:00

# Média diária de irradiância — use este para períodos longos
/medicoes/agregado?estacao=gaic_centro&variavel=irradiancia&intervalo=dia

# Última leitura, para o painel em tempo real
/medicoes/ultima?estacao=gaic_centro&variavel=temperatura
```

### Observação para o dashboard

Para gráficos de período longo, usar `/medicoes/agregado`, não `/medicoes`.
Um ano de dados brutos de uma estação passa de meio milhão de registros e
trava a interface. O agregado faz a conta dentro do MongoDB e devolve poucos
pontos.

## Dados de teste

O script `scripts/gerar_dados_teste.py` cria estações e medições falsas no
formato do projeto, para desenvolver sem depender da entrega do ETL. Ele
simula curva solar, ciclo de temperatura ao longo do dia e também falhas de
medição (cerca de 3% dos registros vêm sem valor), justamente para testar se
a API e o dashboard aguentam dado faltando.

As coordenadas das estações no script são aproximadas e precisam ser
substituídas pelas reais.

## Pendências com o grupo

| Pendência | Com quem |
|---|---|
| O ETL grava direto no Mongo ou entrega arquivo? | Poli |
| Dado faltando vem como `null` ou o registro não vem? | Poli |
| Volume estimado do histórico completo | Poli |
| Código fixo de cada estação | Júlia |
| Latitude, longitude e altitude reais das estações | Júlia / coleta |
| Quais variáveis cada estação mede de fato | Vanessa, Murilo, Carol |
| Frequência de coleta e intervalo de reamostragem | Júlia / Poli |
| Confirmar que o dashboard consome a API, não o Mongo direto | Diovana |
