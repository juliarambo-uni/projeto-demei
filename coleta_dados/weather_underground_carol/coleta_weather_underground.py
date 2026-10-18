
import csv
from pathlib import Path
from datetime import datetime, timedelta

from fontes.csv_manual import obter_dados


pasta = Path(__file__).resolve().parent
pasta_dados = pasta / "dados_brutos"

arquivo_final = pasta_dados / (
    "weather_underground_IIJU2_2026-10-01_a_2026-10-08.csv"
)


def consolidar_csvs():
    arquivos = sorted(
        pasta_dados.glob("weather-history-2026-10-*.csv")
    )

    # Considera somente os dias 1 a 8 de outubro
    arquivos = [
        arquivo for arquivo in arquivos
        if 1 <= int(arquivo.stem[-2:]) <= 8
    ]

    if not arquivos:
        print("Nenhum CSV encontrado.")
        return

    colunas = None
    escritor = None
    total = 0

    with open(
        arquivo_final, "w", encoding="utf-8-sig", newline=""
    ) as saida:

        for arquivo in arquivos:
            # Obtém a data a partir do nome do arquivo diário
            data = datetime.strptime(
                arquivo.stem.replace("weather-history-", ""),
                "%Y-%m-%d"
            ).date().isoformat()

            with open(
                arquivo, "r", encoding="utf-8-sig", newline=""
            ) as entrada:

                leitor = csv.DictReader(entrada)

                if not leitor.fieldnames:
                    print(f"Arquivo sem cabeçalho: {arquivo.name}")
                    continue

                if colunas is None:
                    colunas = leitor.fieldnames

                    escritor = csv.DictWriter(
                        saida,
                        fieldnames=["Date"] + colunas
                    )
                    escritor.writeheader()

                elif leitor.fieldnames != colunas:
                    print(f"Colunas diferentes: {arquivo.name}")
                    continue

                quantidade = 0

                for linha in leitor:
                    # Adiciona a data correspondente a cada registro
                    registro = {"Date": data, **linha}
                    escritor.writerow(registro)
                    quantidade += 1

                total += quantidade
                print(
                    f"{arquivo.name}: {quantidade} registros"
                )

    print(f"\nTotal de registros: {total}")
    print(f"Arquivo criado: {arquivo_final.name}")


def verificar_horarios():
    arquivos = sorted(
        pasta_dados.glob("weather-history-2026-10-*.csv")
    )

    # Verifica somente os dias 1 a 8 de outubro
    arquivos = [
        arquivo for arquivo in arquivos
        if 1 <= int(arquivo.stem[-2:]) <= 8
    ]

    print("\nVERIFICAÇÃO DOS HORÁRIOS")

    for arquivo in arquivos:
        data = datetime.strptime(
            arquivo.stem.replace("weather-history-", ""),
            "%Y-%m-%d"
        ).date()

        with open(
            arquivo, "r", encoding="utf-8-sig", newline=""
        ) as entrada:
            leitor = csv.DictReader(entrada)
            linhas = list(leitor)

        horarios = []

        for linha in linhas:
            try:
                hora = datetime.strptime(
                    linha["Time"].strip(), "%I:%M %p"
                ).time()

                horarios.append(datetime.combine(data, hora))

            except (ValueError, KeyError):
                print(f"Horário inválido em {arquivo.name}")

        duplicados = len(horarios) - len(set(horarios))

        fora_de_ordem = any(
            atual <= anterior
            for anterior, atual in zip(
                horarios, horarios[1:]
            )
        )

        intervalos = []
        ordenados = sorted(set(horarios))

        for anterior, atual in zip(
            ordenados, ordenados[1:]
        ):
            diferenca = atual - anterior

            if diferenca != timedelta(minutes=15):
                intervalos.append(
                    f"{anterior:%H:%M} até {atual:%H:%M}: "
                    f"{diferenca.total_seconds() / 60:.0f} minutos"
                )

        print(f"\n{arquivo.name}")
        print(f"Registros: {len(linhas)}")
        print(f"Horários duplicados: {duplicados}")
        print(
            f"Fora de ordem: {'Sim' if fora_de_ordem else 'Não'}"
        )

        if intervalos:
            print("Intervalos diferentes de 15 minutos:")

            for intervalo in intervalos:
                print(f"- {intervalo}")
        else:
            print("Todos os intervalos são de 15 minutos.")


if __name__ == "__main__":
    consolidar_csvs()
    verificar_horarios()

    dados = obter_dados()

    print("\nTESTE DA COLETA")
    print(f"Registros carregados: {len(dados)}")

    if dados:
        print("Primeiro registro:")
        print(dados[0])
