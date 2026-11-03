"""Carrega no MongoDB um arquivo de dados entregue pelo ETL.

Aceita CSV ou JSON, confere se o conteúdo bate com o padrão do projeto
(`integração_julia/padrao_dados.md`) e só então grava.

A gravação usa upsert na chave única (estacao + timestamp + variavel + fonte),
então rodar o mesmo arquivo duas vezes não duplica nada.

Uso:
    python scripts/importar_dados.py dados.csv
    python scripts/importar_dados.py dados.json
    python scripts/importar_dados.py dados.csv --simular
    python scripts/importar_dados.py dados.csv --ignorar-erros

Opções:
    --simular         Confere o arquivo e mostra o resultado SEM gravar nada.
    --ignorar-erros   Grava as linhas boas e pula as ruins (o padrão é não
                      gravar nada se houver erro).
    --max-erros N     Quantos erros mostrar na tela (padrão 20).

Formato esperado de cada registro:

    estacao      texto, código fixo da estação      (obrigatório)
    timestamp    data/hora com fuso, ex.: 2026-10-12T14:00:00-03:00
    variavel     uma das variáveis do padrão        (obrigatório)
    valor        número, ou vazio quando faltar a medição
    unidade      texto; se vier vazio, é preenchido pela tabela do padrão
    fonte        texto, ex.: GAIC                   (obrigatório)
    tipo_dado    medido, tratado ou estimado        (obrigatório)

No CSV, célula vazia na coluna `valor` significa medição faltando (null).
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo import UpdateOne  # noqa: E402
from pymongo.errors import BulkWriteError  # noqa: E402

from api.db import medicoes, para_utc, testar_conexao  # noqa: E402
from api.schemas import UNIDADES, VARIAVEIS  # noqa: E402

TIPOS_DADO = ("medido", "tratado", "estimado")
CAMPOS_OBRIGATORIOS = ("estacao", "timestamp", "variavel", "fonte", "tipo_dado")

# Quantas operações mandar ao banco por vez.
TAMANHO_LOTE = 2000


class ErroDeLinha(Exception):
    """Problema encontrado em um registro do arquivo."""


def ler_arquivo(caminho: Path) -> list[dict[str, Any]]:
    """Lê o arquivo e devolve a lista de registros crus."""
    sufixo = caminho.suffix.lower()

    if sufixo == ".json":
        with caminho.open(encoding="utf-8-sig") as arquivo:
            conteudo = json.load(arquivo)
        if isinstance(conteudo, dict):
            # Aceita {"collection_medicoes": [...]} ou {"medicoes": [...]}
            for chave in ("collection_medicoes", "medicoes", "dados"):
                if chave in conteudo:
                    conteudo = conteudo[chave]
                    break
            else:
                raise SystemExit(
                    "O JSON é um objeto e não achei a lista de registros dentro "
                    "dele. Esperado: uma lista, ou um objeto com a chave "
                    "'medicoes'."
                )
        if not isinstance(conteudo, list):
            raise SystemExit("O JSON precisa conter uma lista de registros.")
        return conteudo

    if sufixo in (".csv", ".txt"):
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            amostra = arquivo.read(8192)
            arquivo.seek(0)
            try:
                dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
            except csv.Error:
                dialeto = csv.excel
            return list(csv.DictReader(arquivo, dialect=dialeto))

    raise SystemExit(f"Extensão não suportada: {sufixo}. Use .csv ou .json")


def _texto(registro: dict, campo: str) -> str:
    valor = registro.get(campo)
    if valor is None:
        return ""
    return str(valor).strip()


def _numero(bruto: Any) -> float | None:
    """Converte o campo `valor`. Vazio vira None (medição faltando)."""
    if bruto is None:
        return None
    if isinstance(bruto, (int, float)):
        return float(bruto)

    texto = str(bruto).strip()
    if texto == "" or texto.lower() in ("null", "none", "nan", "na"):
        return None

    # Aceita vírgula decimal, comum em arquivo gerado no Brasil.
    try:
        return float(texto.replace(",", "."))
    except ValueError as erro:
        raise ErroDeLinha(f"valor não é número: {bruto!r}") from erro


def validar(registro: dict, numero_linha: int) -> dict[str, Any]:
    """Confere um registro e devolve o documento pronto para o banco."""
    for campo in CAMPOS_OBRIGATORIOS:
        if not _texto(registro, campo):
            raise ErroDeLinha(f"campo obrigatório vazio ou ausente: {campo}")

    variavel = _texto(registro, "variavel")
    if variavel not in VARIAVEIS:
        raise ErroDeLinha(
            f"variável desconhecida: {variavel!r}. "
            f"Use uma destas: {', '.join(VARIAVEIS)}"
        )

    tipo_dado = _texto(registro, "tipo_dado")
    if tipo_dado not in TIPOS_DADO:
        raise ErroDeLinha(
            f"tipo_dado inválido: {tipo_dado!r}. Use: {', '.join(TIPOS_DADO)}"
        )

    bruto_timestamp = _texto(registro, "timestamp")
    try:
        momento = datetime.fromisoformat(bruto_timestamp.replace("Z", "+00:00"))
    except ValueError as erro:
        raise ErroDeLinha(
            f"timestamp não entendido: {bruto_timestamp!r}. "
            "Esperado algo como 2026-10-12T14:00:00-03:00"
        ) from erro

    if momento.tzinfo is None:
        raise ErroDeLinha(
            f"timestamp sem fuso: {bruto_timestamp!r}. "
            "Precisa terminar com o fuso, ex.: -03:00"
        )

    unidade = _texto(registro, "unidade") or UNIDADES[variavel]
    if unidade != UNIDADES[variavel]:
        raise ErroDeLinha(
            f"unidade errada para {variavel}: veio {unidade!r}, "
            f"o padrão é {UNIDADES[variavel]!r}"
        )

    return {
        "estacao": _texto(registro, "estacao"),
        "timestamp": para_utc(momento),
        "variavel": variavel,
        "valor": _numero(registro.get("valor")),
        "unidade": unidade,
        "fonte": _texto(registro, "fonte"),
        "tipo_dado": tipo_dado,
    }


def gravar(documentos: Iterable[dict]) -> tuple[int, int]:
    """Grava os documentos em lotes. Devolve (novos, atualizados)."""
    novos = 0
    atualizados = 0
    lote: list[UpdateOne] = []

    def despachar(operacoes: list[UpdateOne]) -> tuple[int, int]:
        if not operacoes:
            return 0, 0
        try:
            resultado = medicoes.bulk_write(operacoes, ordered=False)
        except BulkWriteError as erro:
            detalhes = erro.details or {}
            resultado = detalhes.get("writeErrors", [])
            print(f"  aviso: {len(resultado)} operações falharam neste lote")
            return 0, 0
        return len(resultado.upserted_ids), resultado.modified_count

    for documento in documentos:
        lote.append(
            UpdateOne(
                {
                    "estacao": documento["estacao"],
                    "timestamp": documento["timestamp"],
                    "variavel": documento["variavel"],
                    "fonte": documento["fonte"],
                },
                {"$set": documento},
                upsert=True,
            )
        )
        if len(lote) >= TAMANHO_LOTE:
            a, b = despachar(lote)
            novos += a
            atualizados += b
            print(f"  {novos + atualizados} registros processados...")
            lote = []

    a, b = despachar(lote)
    return novos + a, atualizados + b


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carrega no MongoDB um arquivo de dados do ETL."
    )
    parser.add_argument("arquivo", type=Path, help="Caminho do .csv ou .json")
    parser.add_argument(
        "--simular",
        action="store_true",
        help="Confere o arquivo e mostra o resultado sem gravar nada",
    )
    parser.add_argument(
        "--ignorar-erros",
        action="store_true",
        help="Grava as linhas boas e pula as ruins",
    )
    parser.add_argument(
        "--max-erros", type=int, default=20, help="Quantos erros mostrar (padrão 20)"
    )
    argumentos = parser.parse_args()

    if not argumentos.arquivo.exists():
        raise SystemExit(f"Arquivo não encontrado: {argumentos.arquivo}")

    print(f"Lendo {argumentos.arquivo}...")
    registros = ler_arquivo(argumentos.arquivo)
    print(f"{len(registros)} registros no arquivo.\n")

    documentos: list[dict] = []
    erros: list[str] = []

    for indice, registro in enumerate(registros, start=1):
        try:
            documentos.append(validar(registro, indice))
        except ErroDeLinha as erro:
            erros.append(f"  linha {indice}: {erro}")

    if erros:
        print(f"{len(erros)} registros com problema:")
        for linha in erros[: argumentos.max_erros]:
            print(linha)
        if len(erros) > argumentos.max_erros:
            print(f"  ... e mais {len(erros) - argumentos.max_erros}")
        print()

        if not argumentos.ignorar_erros and not argumentos.simular:
            print("Nada foi gravado. Corrija o arquivo, ou rode de novo com")
            print("--ignorar-erros para gravar só as linhas boas.")
            raise SystemExit(1)

    vazios = sum(1 for d in documentos if d["valor"] is None)
    estacoes_vistas = sorted({d["estacao"] for d in documentos})
    variaveis_vistas = sorted({d["variavel"] for d in documentos})

    print(f"{len(documentos)} registros válidos")
    print(f"  {vazios} sem valor (medição faltando)")
    print(f"  estações: {', '.join(estacoes_vistas) or '—'}")
    print(f"  variáveis: {', '.join(variaveis_vistas) or '—'}")

    if documentos:
        inicio = min(d["timestamp"] for d in documentos)
        fim = max(d["timestamp"] for d in documentos)
        print(f"  período: {inicio:%d/%m/%Y %H:%M} até {fim:%d/%m/%Y %H:%M} (UTC)")
    print()

    if argumentos.simular:
        print("Modo simulação: nada foi gravado.")
        return

    if not documentos:
        print("Nenhum registro válido para gravar.")
        raise SystemExit(1)

    if not testar_conexao():
        print("Não consegui conectar no banco. Confere o MONGO_URI no .env")
        raise SystemExit(1)

    print("Gravando...")
    novos, atualizados = gravar(documentos)
    print(f"\nPronto: {novos} novos, {atualizados} atualizados.")
    if erros:
        print(f"{len(erros)} linhas foram puladas por erro.")


if __name__ == "__main__":
    main()
