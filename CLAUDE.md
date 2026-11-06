# cotacoes-b3

Cotações de fechamento da B3, atualizadas por GitHub Actions a partir do arquivo oficial COTAHIST.

Para obter cotações:
- `data/ultimo.csv`: último pregão disponível (ações, FIIs, ETFs, BDRs, opções call/put).
- `data/historico/AAAA/vista_AAAA-MM.csv`: histórico diário do mercado à vista, um arquivo por mês (desde jan/2020).
- `data/status.json`: data do último pregão e erros da última execução. Confira `ultimo_pregao` antes de usar.

Colunas: data, ticker, mercado (vista/call/put), especificacao, abertura, maxima, minima, media, fechamento, negocios, quantidade, volume (R$), strike, vencimento, isin.

Preços não são ajustados por proventos/desdobramentos.

Carga histórica: criar `carga_pendente.txt` com os anos (um por linha) e dar push; o workflow processa e apaga o arquivo.

O COTAHIST só traz ativos negociados no dia.
