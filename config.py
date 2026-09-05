import os
from dotenv import load_dotenv
load_dotenv()

POKETRACE_KEY  = os.getenv("POKETRACE_API_KEY", "")
POKETRACE_PLAN = os.getenv("POKETRACE_PLAN", "free").lower()
PPT_KEY        = os.getenv("PPT_API_KEY", "")
PPT_PLAN       = os.getenv("PPT_PLAN", "free").lower()
DB_PATH        = os.getenv("DB_PATH", "pokevalor.db")
OUTPUT_JSON    = os.getenv("OUTPUT_JSON", "../dados.json")
ITENS_JSON     = os.getenv("ITENS_JSON", "../itens.json")   # fonte dos itens (editável no GitHub ou exportado da app)
BUDGET_POKETRACE = int(os.getenv("DAILY_BUDGET_POKETRACE", "240"))
BUDGET_PPT       = int(os.getenv("DAILY_BUDGET_PPT", "90"))

# Capacidades por plano — o código consulta isto, nunca "adivinha".
CAPS = {
    "poketrace": {
        "eu_market":  POKETRACE_PLAN != "free",   # Cardmarket/EUR
        "graded":     POKETRACE_PLAN != "free",   # PSA/BGS/CGC
        "history":    POKETRACE_PLAN != "free",
        "listings":   POKETRACE_PLAN != "free",   # vendas reais eBay item a item
    },
    "ppt": {
        "sealed":     PPT_PLAN in ("api", "business"),
        "japanese":   PPT_PLAN in ("api", "business"),
        "history_days": {"free": 3, "api": 180, "business": 365}.get(PPT_PLAN, 3),
        "cardmarket": PPT_PLAN == "business",
    },
}
