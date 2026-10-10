from gaic_coletor import obter_dados_gaic

resultado = obter_dados_gaic(horas=24)
leituras = resultado["leituras"]   # lista, uma por horário
atual = leituras[-1]               # a mais recente
print(atual["temperatura"])