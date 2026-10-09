"""Cria os índices do banco. Pode rodar quantas vezes quiser.

Uso:
    python scripts/criar_indices.py
"""

import sys
from pathlib import Path

# Permite rodar este script de qualquer lugar: coloca a raiz do projeto
# (a pasta BD_api_matheus) no caminho de busca do Python.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.db import criar_indices, estacoes, medicoes, testar_conexao  # noqa: E402

if __name__ == "__main__":
    if not testar_conexao():
        print("Não consegui conectar no banco. Confere o MONGO_URI no .env")
        raise SystemExit(1)

    criar_indices()
    print("Índices criados.\n")

    for nome, colecao in (("medicoes", medicoes), ("estacoes", estacoes)):
        print(f"{nome}:")
        for indice in colecao.list_indexes():
            print(f"  - {indice['name']}: {dict(indice['key'])}")
