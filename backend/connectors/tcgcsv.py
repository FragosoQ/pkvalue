"""TCGCSV — espelho gratuito e sem chave dos preços TCGplayer (tcgcsv.com).
É a única fonte gratuita que cobre PRODUTO SELADO (booster box, ETB), que nem o
catálogo pokemontcg.io nem o plano free do PokemonPriceTracker dão.

Categoria 3 = Pokémon. Endpoints usados:
  /tcgplayer/3/groups              -> sets (groupId, name, abbreviation)
  /tcgplayer/3/{groupId}/products  -> produtos do set (productId, name)
  /tcgplayer/3/{groupId}/prices    -> preços (productId, marketPrice, subTypeName)

Tudo aqui é best-effort: qualquer falha levanta e o job apanha, nunca interrompe a recolha.
Verificar à mão:  python -m connectors.tcgcsv "Evolving Skies"
"""
import re, time, logging, requests

log = logging.getLogger("tcgcsv")
BASE = "https://tcgcsv.com/tcgplayer/3"
_cache = {}

def _get(path):
    if path in _cache: return _cache[path]
    ult = None
    for tent in range(3):
        try:
            r = requests.get(f"{BASE}{path}", timeout=60)
            r.raise_for_status()
            d = r.json()
            res = d.get("results", d if isinstance(d, list) else [])
            _cache[path] = res
            return res
        except Exception as e:
            ult = e; time.sleep(2 * (tent + 1))
    raise ult

def _norm(s):
    """Compara nomes de set ignorando pontuação, acentos ASCII e prefixos de bloco."""
    s = (s or "").lower()
    s = re.sub(r"\b(pokemon|pok[eé]mon|tcg|sword\s*&?\s*shield|scarlet\s*&?\s*violet|sun\s*&?\s*moon|xy|swsh|sv)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def grupos():
    return _get("/groups")

def grupo_do_set(set_nome):
    """Encontra o groupId do set. Exige correspondência exata do nome normalizado ou
    que um contenha o outro — nunca adivinha por semelhança vaga."""
    alvo = _norm(set_nome)
    if not alvo: return None
    exatos, parciais = [], []
    for g in grupos():
        n = _norm(g.get("name"))
        if not n: continue
        if n == alvo: exatos.append(g)
        elif alvo in n or n in alvo: parciais.append(g)
    if exatos: return exatos[0]
    return parciais[0] if len(parciais) == 1 else None

# Como o TCGplayer nomeia cada tipo de produto selado.
PADROES = {
    "Booster box":   (r"booster box", r"case|display case|blister|bundle|sleeved|single pack"),
    "ETB":           (r"elite trainer box", r"case"),
    "Booster pack":  (r"booster pack", r"box|case|blister|bundle"),
    "Coleção / Tin": (r"\btin\b|collection box", r"case"),
}

def produto_selado(set_nome, tipo):
    """Devolve (produto, preco_dict) do produto selado do tipo pedido nesse set, ou (None, None)."""
    inc, exc = PADROES.get(tipo, (None, None))
    if not inc: return None, None
    g = grupo_do_set(set_nome)
    if not g: return None, None
    gid = g.get("groupId")
    cands = [p for p in _get(f"/{gid}/products")
             if re.search(inc, p.get("name") or "", re.I) and not re.search(exc, p.get("name") or "", re.I)]
    if not cands: return None, None
    precos = {}
    for pr in _get(f"/{gid}/prices"):
        v = pr.get("marketPrice") or pr.get("midPrice") or pr.get("lowPrice")
        if v: precos.setdefault(pr["productId"], pr)
    for p in sorted(cands, key=lambda x: len(x.get("name") or "")):   # o nome mais curto é o produto base
        pr = precos.get(p.get("productId"))
        if pr: return p, pr
    return None, None

def preco(set_nome, tipo):
    """Linha normalizada, no mesmo formato dos outros conectores. None se não houver."""
    p, pr = produto_selado(set_nome, tipo)
    if not pr: return None
    v = pr.get("marketPrice") or pr.get("midPrice") or pr.get("lowPrice")
    return dict(fonte="tcgcsv", tier="MARKET", preco=float(v), low=pr.get("lowPrice"), high=pr.get("highPrice"),
                mercado="US", moeda="USD", raw={"productId": p.get("productId"), "nome": p.get("name")})

if __name__ == "__main__":
    import sys, json
    logging.basicConfig(level=logging.INFO)
    s = sys.argv[1] if len(sys.argv) > 1 else "Evolving Skies"
    print("grupos:", len(grupos()))
    g = grupo_do_set(s); print("grupo:", g and g.get("name"), g and g.get("groupId"))
    for tipo in ("Booster box", "ETB"):
        print(tipo, "->", json.dumps(preco(s, tipo), ensure_ascii=False))
