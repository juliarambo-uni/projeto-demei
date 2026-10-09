# Coleta Weather Underground

## O que foi feito

Pesquisei sobre a API do Weather Underground para verificar a possibilidade de coletar os dados automaticamente, mas ainda não temos uma chave de acesso para utilizá-la. Por enquanto, baixei manualmente os arquivos CSV da estação IIJU2, de Ijuí, referentes aos dias 1º a 8 de outubro de 2026.

Criei um código em Python para juntar os arquivos em um único CSV, conferir os horários e carregar os dados por meio da função `obter_dados()`. Ao todo, foram carregados 768 registros. Durante a verificação, encontrei alguns intervalos diferentes de 15 minutos no dia 3 de outubro. Mantive os horários originais, sem fazer alterações nos dados.

**Por enquanto, a coleta está funcionando por arquivos CSV baixados manualmente.**
