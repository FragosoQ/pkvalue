"""PokemonPriceTracker — /api/v2, header Authorization: Bearer.
Free: 100 créditos/dia, 3 dias histórico. API: selado + JP + 6 meses. Business: Cardmarket EUR."""
import requests
from config import PPT_KEY, CAPS
BASE = "https://www.pokemonpricetracker.com/api/v2"
H = {"Authorization": f"Bearer {PPT_KEY}"}

def _get(path, **params):
    r = requests.get(f"{BASE}{path}", headers=H, params=params, timeout=20)
    r.raise_for_status(); return r.json()

def pesquisar_cartas(termo, limit=5, include_ebay=False):
    p = dict(search=termo, limit=limit)
    if include_ebay: p["includeEbay"] = "true"
    return _get("/cards", **p).get("data", [])

def carta_por_tcgplayer(tcgplayer_id, history_days=None):
    p = dict(tcgPlayerId=tcgplayer_id)
    if history_days:
        p.update(includeHistory="true", days=min(history_days, CAPS["ppt"]["history_days"]))
    d = _get("/cards", **p).get("data", []); return d[0] if d else None

def selados(set_id):
    if not CAPS["ppt"]["sealed"]:
        raise PermissionError("Produtos selados exigem plano API ou Business no PokemonPriceTracker (PPT_PLAN=api).")
    return _get("/sealed-products", setId=set_id, sortBy="price").get("data", [])

def sets(): return _get("/sets", sortBy="releaseDate", sortOrder="desc").get("data", [])

def extrai_precos(card):
    pr = card.get("prices") or {}
    out = []
    if pr.get("market") is not None:
        out.append(dict(fonte="tcgplayer", tier="MARKET", preco=pr["market"], low=pr.get("low"),
                        vendas=pr.get("sellers"), mercado="US", moeda="USD", raw=pr))
    for g in ("psa10", "psa9", "psa8"):
        if card.get(g) is not None:
            out.append(dict(fonte="ebay", tier=g.upper(), preco=card[g], mercado="US", moeda="USD", raw={}))
    return out
