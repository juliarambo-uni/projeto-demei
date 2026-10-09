"""Configurações da aplicação, lidas do arquivo .env."""

import os

from dotenv import load_dotenv

load_dotenv()

# String de conexão do MongoDB (Atlas ou local).
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# Nome do banco de dados do projeto.
MONGO_DB = os.getenv("MONGO_DB", "demei")

# Nome das collections.
COLLECTION_MEDICOES = "medicoes"
COLLECTION_ESTACOES = "estacoes"

# Fuso horário do projeto (UTC-3), conforme definido em padrao_dados.md.
FUSO_PROJETO = "America/Sao_Paulo"

# Limite máximo de registros que a API devolve em uma única página.
LIMITE_MAXIMO = 5000
LIMITE_PADRAO = 1000
