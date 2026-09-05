"""Mesma fórmula da app HTML — mantida aqui como fonte de verdade."""
import datetime as dt

SELADO = {"Booster box", "Booster pack", "ETB", "Coleção / Tin"}

def tendencia(snaps):
    """Variação % entre o primeiro e o último preço de referência; usa avg30d quando só há um dia."""
    ref = [s for s in snaps if s["preco"] is not None]
    if not ref: return None
    if len({s["data"] for s in ref}) >= 2:
        first = [s for s in ref if s["data"] == ref[0]["data"]][0]["preco"]
        last  = [s for s in ref if s["data"] == ref[-1]["data"]][0]["preco"]
        return (last - first) / first * 100 if first else None
    s = ref[-1]
    if s.get("avg30d"): return (s["preco"] - s["avg30d"]) / s["avg30d"] * 100
    return None

def preco_atual(snaps, preferir=("cardmarket", "ebay", "tcgplayer")):
    ult = [s for s in snaps if s["data"] == snaps[-1]["data"]] if snaps else []
    for f in preferir:
        for s in ult:
            if s["fonte"].startswith(f) and s["preco"] is not None: return s["preco"], s["moeda"]
    return (ult[0]["preco"], ult[0]["moeda"]) if ult else (None, None)

def meses_desde(iso):
    if not iso: return None
    try:
        y, m = int(iso[:4]), int(iso[5:7]) if len(iso) >= 7 else 1
        h = dt.date.today(); return (h.year - y) * 12 + (h.month - m)
    except Exception: return None

def escassez(item, snaps):
    """0–30 pontos, calculados a partir de indicadores indiretos de tiragem.
    Se esc_override (1–5) estiver definido, manda ele: esc_override*6."""
    if item.get("esc_override"): return item["esc_override"] * 6, {"override": True}
    det = {}
    det["producao"] = {"em": 0, "fim_anunciado": 5, "fora": 10}.get(item.get("producao") or "em", 0)
    m = meses_desde(item.get("ultima_reimpressao") or (f"{item['ano']}-01" if item.get("ano") else None))
    det["reimpressao"] = 0 if m is None else min(8, (m // 6) * 2)
    det["tipo_set"] = {"principal": 0, "especial": 3, "promo": 5}.get(item.get("tipo_set") or "principal", 0)
    pop = item.get("pop_psa10")
    det["populacao"] = 2 if pop in (None, "") else (0 if pop > 5000 else 1 if pop > 2000 else 3 if pop > 1000 else 4 if pop > 500 else 5)
    det["racio"] = racio_vendas_oferta(snaps)
    return sum(det.values()), det

def racio_vendas_oferta(snaps):
    """0–2: vendas recentes vs anúncios ativos (quando a API dá ambos). 1 = neutro/desconhecido."""
    ult = [s for s in snaps if s.get("vendas") and s.get("raw")] if snaps else []
    for s in reversed(ult):
        try:
            import json; r = json.loads(s["raw"]) if isinstance(s["raw"], str) else s["raw"]
            listings = r.get("listings") or r.get("sellers")
            if listings: q = s["vendas"] / listings; return 2 if q > 1.0 else 1 if q > 0.4 else 0
        except Exception: pass
    return 1

def score(item, snaps):
    t = tendencia(snaps)
    p_t = 12 if t is None else max(0, min(30, 15 + t / 2))
    p_e, det_e = escassez(item, snaps)
    p_p = item["proc"] * 4
    idade = dt.date.today().year - (item["ano"] or dt.date.today().year)
    p_i = min(10, idade * 2)
    p_tipo = 10 if item["tipo"] in SELADO else (7 if item["tipo"] == "Set completo" else 5)
    s = round(min(100, p_t + p_e + p_p + p_i + p_tipo))
    return s, {"tendencia": t, "pontos": dict(tendencia=p_t, escassez=p_e, procura=p_p, idade=p_i, tipo=p_tipo), "escassez": det_e}

def veredito(s): return "Comprar" if s >= 70 else ("Acompanhar" if s >= 50 else "Evitar")
