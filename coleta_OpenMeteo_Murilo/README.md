# Coletor Open-Meteo — Projeto Integrador DEMEI

Coleta de dados meteorológicos horários da API [Open-Meteo](https://open-meteo.com) para apoiar a previsão de geração fotovoltaica do DEMEI (Ijuí - RS).

Esta etapa do fluxo **só coleta e guarda o dado bruto**, sem transformar nada. A padronização é feita pela etapa seguinte (ETL).

```
Open-Meteo  →  [este módulo]  →  JSON bruto + pacote (metadados + dados)  →  ETL  →  Banco  →  Dashboard
```

---

## 1. Arquivos

| Arquivo | Descrição |
|---|---|
| `coleta_open_meteo_week.py` | Versão **semana**: o padrão do script é coletar **7 dias**. Não define unidades (usa as da API). |
| `coleta_open_meteo_month+.py` | Versão **mês**: o padrão do script é coletar **30 dias** e tem a opção `--dias`. Define as unidades explicitamente. |
| `requirements.txt` | Dependências (`requests`). |

### Diferenças entre as duas versões

| | `..._week.py` | `..._month+.py` |
|---|---|---|
| Janela padrão (script) | 7 dias (168 registros) | 30 dias (720 registros) |
| Opção `--dias` | não tem | **tem** |
| Unidades pedidas à API | não pede (padrão da API) | **pede explicitamente** |
| Velocidade do vento | **km/h** | **m/s** |
| Temperatura / precipitação | °C / mm (padrão da API) | °C / mm (explícito) |
| Função `coletar_open_meteo` | igual | igual (mais as unidades) |

> **Atenção:** o vento sai em unidades diferentes (km/h na `week`, m/s na `month+`). Para o MVP, recomenda-se usar a versão `month+`, que fixa as unidades, e **não misturar** dados das duas versões no mesmo banco sem converter.

---

## 2. Requisitos e instalação

- Python 3.9 ou superior
- Acesso à internet
- Não precisa de chave de API (a Open-Meteo é gratuita para uso não comercial)

Dentro da pasta do projeto, no terminal (no VS Code: *Terminal > Novo Terminal*):

```powershell
pip install -r requirements.txt
```

ou, se preferir:

```powershell
pip install requests
```

Confira que o terminal está **na pasta do projeto** (o caminho antes do `>` deve terminar no nome da pasta). Não é necessário rodar como Administrador.

---

## 3. Como rodar pelo terminal

### 3.1 Versão semana — `coleta_open_meteo_week.py`

**Modo padrão** (últimos 7 dias disponíveis, em Ijuí):

```powershell
python coleta_open_meteo_week.py
```

**Com datas específicas:**

```powershell
python coleta_open_meteo_week.py --inicio 2026-09-01 --fim 2026-09-07
```

### 3.2 Versão mês — `coleta_open_meteo_month+.py`

**Modo padrão** (últimos 30 dias disponíveis, em Ijuí):

```powershell
python coleta_open_meteo_month+.py
```

**Com outra duração** (termina no `--fim` padrão e volta N dias):

```powershell
python coleta_open_meteo_month+.py --dias 90
```

**Com datas específicas:**

```powershell
python coleta_open_meteo_month+.py --inicio 2026-09-01 --fim 2026-09-30
```

### 3.3 Resultado esperado

```
OK: 720 registros horários coletados.
Arquivo: data\raw\open_meteo\open_meteo_OPENMETEO_IJUI_2026-09-01_2026-09-30_20261008T120000Z.json
```

O arquivo JSON é criado em `data/raw/open_meteo/` (a pasta é criada automaticamente).

### 3.4 Mais exemplos (valem para as duas versões)

```powershell
# Um único dia
python coleta_open_meteo_month+.py --inicio 2026-09-15 --fim 2026-09-15

# Outro ponto, outro ID de estação e outra pasta de saída
python coleta_open_meteo_month+.py --inicio 2026-09-01 --fim 2026-09-30 --lat -29.75 --lon -57.09 --estacao-id OPENMETEO_TESTE --pasta data/raw/teste

# Apagar brutos com mais de 7 dias antes de coletar
python coleta_open_meteo_month+.py --limpar-dias 7

# Ver todas as opções
python coleta_open_meteo_month+.py --help
```

---

## 4. Opções do script (linha de comando)

| Opção | O que faz | Padrão | Em qual versão |
|---|---|---|---|
| `--inicio` | Data inicial (`AAAA-MM-DD`) | `week`: `fim - 6 dias` / `month+`: `fim - (dias - 1)` | ambas |
| `--fim` | Data final (`AAAA-MM-DD`) | hoje − 6 dias | ambas |
| `--dias` | Tamanho da janela quando `--inicio` é omitido. Ignorado se `--inicio` for informado | 30 | **só `month+`** |
| `--lat` | Latitude do ponto | -28.388 (Ijuí) | ambas |
| `--lon` | Longitude do ponto | -53.914 (Ijuí) | ambas |
| `--estacao-id` | Identificador da estação nos metadados e no nome do arquivo | `OPENMETEO_IJUI` | ambas |
| `--modo` | `historico` ou `previsao` | `historico` | ambas |
| `--pasta` | Pasta onde salvar o JSON bruto | `data/raw/open_meteo` | ambas |
| `--limpar-dias` | Apaga brutos com mais de N dias antes de coletar | desligado | ambas |

**Regras das datas**
- Formato obrigatório: `AAAA-MM-DD`.
- `--inicio` e `--fim` são **inclusivos** (01/09 a 30/09 = 30 dias = 720 registros horários).
- No modo `historico` a API tem cerca de **5 dias de atraso**; por isso o `--fim` padrão é hoje − 6 dias. Datas muito recentes podem retornar valores `null`.

**Modos**
- `historico`: usa `archive-api.open-meteo.com` (dados passados).
- `previsao`: usa `api.open-meteo.com` (dados recentes e previsão). Aceita apenas janelas curtas próximas da data atual.

---

## 5. Variáveis coletadas e unidades

Todas as variáveis são **horárias**. Os horários (`time`) estão em **UTC** no formato ISO 8601 (ex.: `2026-09-01T00:00`). Horário de Brasília = UTC − 3.

| Variável (nome na API) | Descrição | Unidade (`month+`) | Unidade (`week`) | Tipo de valor |
|---|---|---|---|---|
| `time` | Data e hora | ISO 8601, UTC | ISO 8601, UTC | — |
| `temperature_2m` | Temperatura a 2 m | °C | °C | Instantâneo |
| `relative_humidity_2m` | Umidade relativa a 2 m | % | % | Instantâneo |
| `pressure_msl` | Pressão reduzida ao nível do mar | hPa | hPa | Instantâneo |
| `surface_pressure` | Pressão na superfície | hPa | hPa | Instantâneo |
| `precipitation` | Precipitação (chuva + neve derretida) | mm | mm | **Soma da hora anterior** |
| `cloud_cover` | Cobertura de nuvens | % | % | Instantâneo |
| `wind_speed_10m` | Velocidade do vento a 10 m | **m/s** | **km/h** | Instantâneo |
| `wind_direction_10m` | Direção de onde o vento vem | ° (0–360; 0 = Norte, 90 = Leste) | ° | Instantâneo |
| `shortwave_radiation` | Irradiância global horizontal (GHI) | W/m² | W/m² | **Média da hora anterior** |
| `direct_radiation` | Irradiância direta (plano horizontal) | W/m² | W/m² | Média da hora anterior |
| `diffuse_radiation` | Irradiância difusa | W/m² | W/m² | Média da hora anterior |
| `direct_normal_irradiance` | Irradiância direta normal (DNI) | W/m² | W/m² | Média da hora anterior |

**Convenção importante:** radiação e precipitação referem-se à **hora que terminou** no horário indicado (a linha das `10:00` representa 09:00–10:00). Temperatura, umidade, pressão, nuvens e vento são valores instantâneos. Isso precisa ser considerado ao alinhar com outras fontes.

**Fonte oficial das unidades:** o próprio JSON salvo traz o bloco `dados_brutos.hourly_units` com a unidade de cada variável. Em caso de dúvida, ele vale mais que esta tabela.

### Padrão de unidades sugerido para todo o grupo

| Grandeza | Unidade |
|---|---|
| Temperatura | °C |
| Umidade | % |
| Pressão | hPa |
| Precipitação | mm (por hora) |
| Vento | m/s |
| Direção do vento | graus (0–360) |
| Irradiância | W/m² |
| Data/hora | ISO 8601 em UTC |

---

## 6. A função principal: `coletar_open_meteo`

É a função que o sistema deve chamar. Existe nas duas versões com a mesma assinatura.

```python
coletar_open_meteo(
    data_inicio,
    data_fim,
    latitude=-28.388,
    longitude=-53.914,
    variaveis=None,
    estacao_id="OPENMETEO_IJUI",
    modo="historico",
    salvar=True,
    pasta_saida=Path("data/raw/open_meteo"),
)
```

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `data_inicio` | `str` `"AAAA-MM-DD"` ou `date` | Data inicial (inclusiva). **Obrigatório** |
| `data_fim` | `str` ou `date` | Data final (inclusiva). **Obrigatório** |
| `latitude` | `float` | Latitude em graus decimais |
| `longitude` | `float` | Longitude em graus decimais |
| `variaveis` | `list[str]` ou `None` | Variáveis horárias a coletar. `None` usa a lista padrão da tabela da seção 5 |
| `estacao_id` | `str` | Identificador da "estação" no nosso sistema |
| `modo` | `"historico"` ou `"previsao"` | Qual endpoint da API usar |
| `salvar` | `bool` | `True` grava o JSON bruto em disco |
| `pasta_saida` | `str` ou `Path` | Pasta onde gravar o bruto |

### Retorno

Um dicionário com duas chaves:

```python
{
  "metadados": {
      "fonte": "open-meteo",
      "modo": "historico",
      "estacao_id": "OPENMETEO_IJUI",
      "url_requisitada": "https://archive-api.open-meteo.com/v1/archive?...",
      "parametros": { ... },              # parâmetros enviados à API
      "periodo": {"inicio": "2026-09-01", "fim": "2026-09-30"},
      "coletado_em_utc": "2026-10-08T12:00:00+00:00",
      "status_http": 200,
      "total_registros": 720,
      "versao_coletor": "1.0.0",
      "arquivo_bruto": "data/raw/open_meteo/open_meteo_...json"   # None se salvar=False
  },
  "dados_brutos": {                        # JSON original da API, sem alterações
      "latitude": ..., "longitude": ..., "elevation": ...,
      "hourly_units": {"time": "iso8601", "temperature_2m": "°C", ...},
      "hourly": {
          "time": ["2026-09-01T00:00", ...],
          "temperature_2m": [12.3, ...],
          ...
      }
  }
}
```

Os dados horários vêm em **listas paralelas**: a posição `i` de `time` corresponde à posição `i` de cada variável. Valores ausentes aparecem como `null` (`None` em Python).

### Outras funções do arquivo

| Função | Descrição |
|---|---|
| `salvar_bruto(pacote, pasta_saida)` | Grava o pacote em JSON e devolve o caminho. Já é chamada por `coletar_open_meteo` quando `salvar=True` |
| `limpar_brutos_antigos(dias=7, pasta=...)` | Apaga brutos com mais de N dias e devolve quantos apagou |
| `ColetaOpenMeteoError` | Exceção lançada em caso de data inválida, pedido recusado pela API ou falha de rede após 3 tentativas |

### Comportamento da coleta

- **Timeout** de 30 s por requisição.
- Até **3 tentativas** em caso de erro de rede ou do servidor (espera 2 s e depois 4 s).
- Erro 400 (pedido inválido) **não** é repetido; a mensagem da API é exibida.
- Valida se a resposta contém `hourly` e `time`.
- Os dados brutos **não são alterados**. A rastreabilidade fica nos metadados.

---

## 7. Nome do arquivo de saída

```
open_meteo_<ESTACAO_ID>_<INICIO>_<FIM>_<CARIMBO_UTC>.json
```

Exemplo: `open_meteo_OPENMETEO_IJUI_2026-09-01_2026-09-30_20261008T120000Z.json`

O carimbo de data/hora evita sobrescrever coletas anteriores do mesmo período.

---

## 8. Usando a função em outro código do projeto

### Uso direto de um arquivo (script de teste, notebook)

Nomes de arquivo com `+` **não podem ser importados** com `import`/`from ... import`, pois o Python interpreta `+` como operador. Duas saídas:

**Opção recomendada: renomear** o arquivo para um nome válido, por exemplo `coleta_open_meteo.py`, e então:

```python
from coleta_open_meteo import coletar_open_meteo, ColetaOpenMeteoError

try:
    pacote = coletar_open_meteo("2026-09-01", "2026-09-30")
except ColetaOpenMeteoError as erro:
    print("Coleta falhou:", erro)
else:
    print(pacote["metadados"]["total_registros"], "registros")
    dados = pacote["dados_brutos"]["hourly"]
```

**Opção sem renomear** (carregar o arquivo pelo caminho):

```python
import importlib.util

spec = importlib.util.spec_from_file_location("coleta_month", "coleta_open_meteo_month+.py")
coleta_month = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coleta_month)

pacote = coleta_month.coletar_open_meteo("2026-09-01", "2026-09-30")
```

O mesmo vale para `coleta_open_meteo_week.py`, que pode ser importado normalmente como `coleta_open_meteo_week`, já que o nome é válido.

### Teste rápido em uma linha

```powershell
python -c "from coleta_open_meteo_week import coletar_open_meteo; p = coletar_open_meteo('2026-09-01', '2026-09-07'); print(p['metadados']['total_registros'], p['metadados']['arquivo_bruto'])"
```

### Papel no sistema

- Um orquestrador (script agendado ou botão de atualização) chama `coletar_open_meteo` e entrega o `pacote` ao ETL.
- O dashboard **não** deve chamar o coletor; ele apenas lê do banco.
- O caminho padrão de saída é relativo ao diretório de onde o programa roda. Em outro ambiente (ex.: Docker), passe `pasta_saida` explicitamente.

---

## 9. Problemas comuns

| Mensagem / sintoma | Causa provável | Solução |
|---|---|---|
| `can't open file ... No such file or directory` | Terminal fora da pasta do projeto ou nome do arquivo errado | Entre na pasta com `cd` e confira o nome com `dir` |
| `python` não é reconhecido | Python fora do PATH | Use `py` no lugar de `python` ou reinstale marcando "Add Python to PATH" |
| `ModuleNotFoundError: No module named 'requests'` | Biblioteca não instalada nesse Python | `python -m pip install requests` |
| `Data inválida` | Formato errado | Use `AAAA-MM-DD` |
| `data_inicio não pode ser posterior a data_fim` | Datas invertidas | Troque a ordem |
| `Falha após 3 tentativas` | Sem internet, rede bloqueada ou API fora do ar | Teste em outra rede e tente de novo mais tarde |
| `unrecognized arguments: --dias` | Usando a versão `week` | `--dias` existe só na `month+` |
| Valores `null` no fim da série | Atraso da API histórica | Use `--fim` com pelo menos 6 dias atrás |
| Vento com valores "grandes" | Versão `week` entrega km/h | Use a `month+` (m/s) ou converta (km/h ÷ 3,6 = m/s) |

---

## 10. Limitações e observações

- A Open-Meteo entrega dados de **modelos e reanálise** para um ponto de grade, e **não** medições de uma estação física. Isso deve constar na documentação do projeto como característica da fonte.
- A resolução é horária.
- Os dados brutos em `data/raw/` são **temporários**; use `--limpar-dias` ou `limpar_brutos_antigos` para controlar o espaço. O histórico consolidado fica no banco de dados.
- Uso gratuito da API restrito a fins não comerciais; confira os termos em open-meteo.com.

