# Fluxo de Integração do Projeto

## Objetivo

Definir como os dados passam entre as diferentes etapas do projeto,
estabelecendo o que cada etapa recebe, processa e entrega para a próxima.

## Fluxo geral

Fontes de dados
↓
Coleta
↓
Padronização / ETL
↓
MongoDB
↓
API
↓
Dashboard

---

## 1. Fontes de dados → Coleta

As fontes utilizadas no projeto são:

- GAIC/Unijuí
- Open-Meteo
- Weather Underground

Cada responsável pela coleta deverá obter os dados disponíveis em sua
respectiva fonte e manter os dados brutos separados dos dados tratados.

### Entrega da etapa de coleta

Cada responsável deverá entregar:

- código utilizado para realizar a coleta;
- dados brutos obtidos, quando possível;
- identificação da fonte;
- identificação da estação;
- documentação sobre como os dados são obtidos;
- informações sobre as variáveis disponíveis;
- frequência ou intervalo dos dados, quando essa informação estiver disponível.

A etapa de coleta não é responsável por realizar o tratamento completo
dos dados para o formato final do projeto.

---

## 2. Coleta → ETL

A etapa de ETL recebe os dados coletados pelas diferentes fontes.

Os dados podem apresentar diferenças de:

- nomes das variáveis;
- unidades;
- formato de data e hora;
- frequência de coleta;
- estrutura dos arquivos ou respostas das APIs.

O ETL será responsável por transformar esses dados para o padrão definido
no arquivo `padrao_dados.md`.

## Preservação dos dados brutos

Os dados obtidos diretamente das fontes devem ser preservados antes do
tratamento sempre que isso for possível.

O processo de ETL não deve substituir os dados brutos originais. Os dados
tratados deverão ser gerados a partir deles, permitindo identificar a
origem das informações e os tratamentos realizados.

### Entrega da etapa de ETL

Os dados tratados deverão seguir a estrutura padronizada definida pelo
projeto e estar preparados para armazenamento no banco de dados.

---

## 3. ETL → Banco de dados

O ETL entrega ao responsável pelo banco dados já padronizados.

O responsável pelo banco não deve precisar conhecer a estrutura original
de cada fonte.

O banco deverá receber os dados em uma estrutura única, permitindo
consultas por estação, variável e período.

---

## 4. Banco de dados → API

A API será responsável por disponibilizar os dados armazenados no banco
para as outras partes do sistema.

As consultas deverão permitir, conforme a implementação:

- filtrar por estação;
- filtrar por variável;
- filtrar por período.

A API deve retornar os dados em uma estrutura consistente para consumo
pelo dashboard.

---

## 5. API → Dashboard

O dashboard utilizará a API para consultar os dados.

O dashboard não deverá depender diretamente dos arquivos brutos das
fontes nem realizar o tratamento principal dos dados.

A visualização deverá permitir, conforme a implementação:

- selecionar estação;
- selecionar período;
- selecionar variável;
- visualizar os dados em gráficos;
- visualizar as estações em um mapa, quando possível.

---

## Responsabilidades resumidas

| Etapa | Responsável | Principal responsabilidade |
|---|---|---|
| Integração | Júlia | Organizar padrões e integração entre as etapas |
| GAIC | Vanessa | Coletar dados do GAIC/Unijuí |
| Open-Meteo | Murilo | Coletar dados do Open-Meteo |
| Weather Underground | Carol | Coletar dados do Weather Underground |
| ETL | Poli | Padronizar e tratar os dados |
| Banco/API | Matheus | Armazenar e disponibilizar os dados |
| Dashboard | Diovana | Criar a interface e visualização |

## Regra principal

Cada etapa deve entregar seus dados e componentes de forma que a próxima
etapa consiga utilizá-los sem precisar conhecer os detalhes internos da
etapa anterior.