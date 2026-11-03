# Dashboard meteorológico — Diovana

Dashboard em Streamlit para visualizar os dados meteorológicos padronizados do projeto DEMEI. A aplicação consome exclusivamente a API FastAPI (`BD_api_matheus`) — não acessa o MongoDB nem lê arquivos brutos diretamente.

## Funcionalidades

- Seleção de variável, estação, período e resolução horária/diária/mensal;
- Série temporal com média e faixa mínima/máxima;
- Comparação da estação de referência com até duas outras estações/fontes;
- Indicadores-resumo e quadro de cobertura da API;
- Mapa das estações cadastradas e tabela de coordenadas;
- Exportação das medições brutas filtradas para CSV, com paginação da API e limite de segurança de 100 mil linhas.

## Executar o projeto completo com Docker

Na raiz do repositório:

```bash
docker compose -f BD_api_matheus/docker-compose.yml up --build -d
```

- Dashboard: <http://localhost:8501>
- API: <http://localhost:8000/docs>
- MongoDB: `localhost:27017`

O Compose inicia MongoDB, API e dashboard. O dashboard espera a API ficar saudável antes de iniciar. Os dados não são inseridos automaticamente.

### Cadastrar estações e carregar dados reais

O serviço da API inclui os scripts do responsável pelo banco. O diretório padronizado do ETL é montado em `/dados_padronizados` dentro do container.

```bash
docker compose -f BD_api_matheus/docker-compose.yml exec api python scripts/criar_indices.py
docker compose -f BD_api_matheus/docker-compose.yml exec api python scripts/cadastrar_estacoes.py estacoes.csv
```

Para importar um arquivo JSON ou CSV produzido pelo ETL, substitua pelo nome do arquivo que estiver em `processamento_etl_poli/dados_padronizados`:

```bash
docker compose -f BD_api_matheus/docker-compose.yml exec api \
  python scripts/importar_dados.py /dados_padronizados/SEU_ARQUIVO.json
```

O arquivo já versionado no repositório também pode ser usado para uma demonstração:

```bash
docker compose -f BD_api_matheus/docker-compose.yml exec api \
  python scripts/importar_dados.py \
  /dados_padronizados/medicoes_padronizadas_2025-09-30_2026-10-14_1428.json
```

Depois, abra ou atualize <http://localhost:8501>. Se o banco estiver vazio, os filtros continuam disponíveis, mas os gráficos exibem um estado sem dados.

## Executar somente o dashboard localmente

Com a API já iniciada em `localhost:8000`:

```bash
cd dashboard_diovana
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Se a API estiver em outro endereço, defina `API_URL` antes de iniciar:

```bash
API_URL=http://localhost:8000 streamlit run app.py
```

No PowerShell:

```powershell
$env:API_URL = "http://localhost:8000"
streamlit run app.py
```

## Observações

- O intervalo padrão é baseado no período informado por `/cobertura` para a estação e variável selecionadas.
- Consultas de gráficos usam `/medicoes/agregado` para evitar baixar grandes volumes de dados.
- O CSV usa `/medicoes` com paginação, preserva campos de origem e bloqueia exportações acima de 100 mil registros para proteger a aplicação.
- Se a API ou o banco não estiverem acessíveis, a tela informa o endereço de conexão e orienta verificar os serviços.
