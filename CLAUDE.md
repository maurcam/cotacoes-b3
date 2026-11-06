# cotacoes-b3

Cotações de fechamento da B3, atualizadas por GitHub Actions a partir do arquivo oficial COTAHIST.

Para obter cotações:
- `data/ultimo.csv`: último pregão disponível (ações, FIIs, ETFs, BDRs, opções call/put).
- `data/historico/vista_AAAA.csv`: histórico diário do mercado à vista.
- `data/status.json`: data do último pregão e erros da última execução. Confira `ultimo_pregao` antes de usar.

Colunas: data, ticker, mercado (vista/call/put), especificacao, abertura, maxima, minima, media, fechamento, negocios, quantidade, volume (R$), strike, vencimento, isin.

Preços não são ajustados por proventos/desdobramentos.

Carga histórica: rodar o workflow manualmente com o input `ano`.
