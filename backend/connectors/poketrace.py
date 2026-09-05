"""PokeTrace — api.poketrace.com/v1, header X-API-Key.
Free: 250/dia, mercado US, raw. Pro+: EU (Cardmarket/EUR), graduadas, histórico, listings."""
import requests
from config import POKETRACE_KEY, CAPS
BASE = "https://api.poketrace.com/v1"
H = {"X-API-Key": POKETRACE_KEY}

def _get(path, **params):
    r = requests.get(f"{BASE}{path}", headers=H, params=params, timeout=20)
    r.raise_for_status(); return r.json()

def pesquisar(termo, market="US", limit=5):
    if market == "EU" and not CAPS["poketrace"]["eu_market"]: market = "US"
    return _get("/cards", search=termo, market=market, limit=limit).get("data", [])

def carta(card_id):
    return _get(f"/cards/{card_id}").get("data")

def extrai_precos(card):
    """Normaliza a resposta em linhas (fonte, tier, preco, low, high, vendas, avg7d, avg30d)."""
    out = []
    for fonte, tiers in (card.get("prices") or {}).items():
        for tier, p in (tiers or {}).items():
            if not isinstance(p, dict) or p.get("avg") is None: continue
            out.append(dict(fonte=fonte, tier=tier, preco=p["avg"], low=p.get("low"), high=p.get("high"),
                            vendas=p.get("saleCount"), avg7d=p.get("avg7d"), avg30d=p.get("avg30d"),
                            mercado=card.get("market"), moeda=card.get("currency"), raw=p))
    return out
