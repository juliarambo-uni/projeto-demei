"""Apaga os dados do banco. Use antes da primeira carga de dados reais.

O script de teste (`gerar_dados_teste.py`) enche o banco de dados inventados
para desenvolver sem depender do ETL. Quando os dados reais chegam, esses
precisam sair — senão o dashboard mostra estação de verdade e estação
inventada lado a lado, sem jeito de diferenciar.

Mostra o que existe, pede confirmação, e só então apaga.

Uso:
    python scripts/limpar_banco.py                  # mostra e pergunta
    python scripts/limpar_banco.py --medicoes       # só as medições
    python scripts/limpar_banco.py --estacoes       # só o cadastro
    python scripts/limpar_banco.py --sim            # sem perguntar
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.db import estacoes, medicoes, para_fuso_projeto, testar_conexao  # noqa: E402


def resumo() -> tuple[int, int]:
    """Mostra o que existe no banco hoje."""
    total_medicoes = medicoes.count_documents({})
    total_estacoes = estacoes.count_documents({})

    print(f"Medições: {total_medicoes}")
    if total_medicoes:
        por_fonte = medicoes.aggregate(
            [{"$group": {"_id": "$fonte", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]
        )
        for linha in por_fonte:
            print(f"  {linha['_id']}: {linha['n']}")

        primeiro = medicoes.find_one({}, sort=[("timestamp", 1)])
        ultimo = medicoes.find_one({}, sort=[("timestamp", -1)])
        if primeiro and ultimo:
            print(
                f"  período: {para_fuso_projeto(primeiro['timestamp']):%d/%m/%Y} "
                f"até {para_fuso_projeto(ultimo['timestamp']):%d/%m/%Y}"
            )

    print(f"\nEstações cadastradas: {total_estacoes}")
    for documento in estacoes.find({}, {"_id": 0, "estacao": 1, "nome": 1}).sort(
        "estacao", 1
    ):
        print(f"  {documento['estacao']} — {documento.get('nome', '')}")

    return total_medicoes, total_estacoes


def main() -> None:
    parser = argparse.ArgumentParser(description="Apaga os dados do banco.")
    parser.add_argument(
        "--medicoes", action="store_true", help="Apaga só a collection de medições"
    )
    parser.add_argument(
        "--estacoes", action="store_true", help="Apaga só a collection de estações"
    )
    parser.add_argument(
        "--sim", action="store_true", help="Não pergunta, apaga direto"
    )
    argumentos = parser.parse_args()

    if not testar_conexao():
        print("Não consegui conectar no banco. Confere o MONGO_URI no .env")
        raise SystemExit(1)

    # Sem escolha explícita, apaga as duas.
    apagar_medicoes = argumentos.medicoes or not argumentos.estacoes
    apagar_estacoes = argumentos.estacoes or not argumentos.medicoes

    print("Situação atual do banco:\n")
    total_medicoes, total_estacoes = resumo()

    alvos = []
    if apagar_medicoes:
        alvos.append(f"{total_medicoes} medições")
    if apagar_estacoes:
        alvos.append(f"{total_estacoes} estações")

    print(f"\nVai apagar: {' e '.join(alvos)}.")
    print("Isso não tem volta.")

    if not argumentos.sim:
        resposta = input("\nDigite APAGAR para confirmar: ").strip()
        if resposta != "APAGAR":
            print("Cancelado, nada foi apagado.")
            return

    if apagar_medicoes:
        resultado = medicoes.delete_many({})
        print(f"{resultado.deleted_count} medições apagadas.")
    if apagar_estacoes:
        resultado = estacoes.delete_many({})
        print(f"{resultado.deleted_count} estações apagadas.")

    print("\nOs índices continuam no lugar. Pode carregar os dados reais.")


if __name__ == "__main__":
    main()
