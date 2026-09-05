# PokéValor — backend

Recolha diária de preços (PokeTrace + PokemonPriceTracker), base de dados própria, pontuação e `dados.json` para a app HTML.

## Instalar
```
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # preenche as chaves
```
Chaves gratuitas: https://poketrace.com/dashboard e https://www.pokemonpricetracker.com/sign-up

## Usar
```
uvicorn api:app --reload --port 8000     # API para a app (botão "Sincronizar")
python job.py                            # recolha manual; agendar diariamente com cron / Task Scheduler
```
Na app, "Exportar dados" → `POST /itens/importar` (ou usa o botão Sincronizar, que envia e recebe).

## Plano free vs pago
Tudo controlado em `.env` — muda `POKETRACE_PLAN` / `PPT_PLAN` e o código liga as funcionalidades sozinho:

| Funcionalidade | Free | Pago |
|---|---|---|
| Cartas, preço US (TCGplayer, eBay) | sim | sim |
| Cardmarket / EUR | não | PokeTrace Pro (19,99 $) ou PPT Business |
| Graduadas PSA/BGS/CGC | não | PokeTrace Pro |
| Produtos selados (boxes, ETB) | manual na app | PPT API (9,99 $) |
| Histórico | o teu (cresce 1 dia/dia) | + histórico do fornecedor |

Orçamento diário protegido por `DAILY_BUDGET_*`; o uso fica em `uso_api`.

## Ficheiros
- `connectors/` — um ficheiro por fornecedor; acrescenta outro (ex. tcgapi.net) com a mesma interface `extrai_precos`.
- `scoring.py` — fórmula da pontuação (igual à da app).
- `job.py` — recolha + exportação. `api.py` — endpoints locais.
- Os snapshots ficam em SQLite; ao fim de meses tens o teu próprio histórico independente dos planos.
