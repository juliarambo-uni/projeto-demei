"""
Gera um arquivo JSON com os dados tratados da estação do GAIC.

Precisa estar na mesma pasta do gaic_coletor.py e do gaic_tratamento.py,
e das variáveis GAIC_TOKEN e GAIC_LOGGER_SN definidas no terminal.

Uso:
    python gerar_json.py          # últimas 24 horas
    python gerar_json.py 6        # últimas 6 horas
"""

import json
import sys
from datetime import datetime

from gaic_coletor import obter_dados_gaic

horas = float(sys.argv[1]) if len(sys.argv) > 1 else 24

resultado = obter_dados_gaic(horas=horas)

saida = {
    "estacao": "UNIJUI - SEDE (GAIC)",
    "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "periodo_horas": horas,
    "total_leituras": len(resultado["leituras"]),
    "unidades": resultado["unidades"],
    "leituras": resultado["leituras"],
}

nome = f"dados_gaic_{datetime.now():%Y%m%d_%H%M%S}.json"
with open(nome, "w", encoding="utf-8") as f:
    json.dump(saida, f, ensure_ascii=False, indent=2)

print(f"Arquivo gerado: {nome}")
print(f"Leituras: {saida['total_leituras']}")
