"""Cruza previsões passadas com os preços que vieram a seguir.

Duas decisões que fazem a diferença entre uma avaliação honesta e auto-engano:

1. AMOSTRAGEM MENSAL. O job grava uma previsão por item por dia. Avaliar as 365
   previsões de um item a 90 dias não dá 365 observações independentes — dá uma,
   repetida 365 vezes, e infla artificialmente a confiança. Por isso conta-se no
   máximo uma previsão por item por mês.

2. BASELINE DO UNIVERSO. Taxa de acerto isolada não diz nada: num mercado a subir,
   "Comprar" acerta sempre. O que mede se a pontuação vale alguma coisa é o retorno
   médio dos "Comprar" MENOS o retorno médio de todos os itens seguidos (`vantagem`).
   Se a vantagem não for positiva, a heurística não está a acrescentar informação.
"""
import statistics as st, datetime as dt
import scoring

HORIZONTES = (90, 180, 365)
TOL = 30              # aceita a observação mais próxima do horizonte, ±30 dias
AVALIAVEIS = ("Comprar", "Acompanhar", "Evitar")   # "Sem dados"/"Prematuro" não são apostas

def _preco_no_horizonte(sr, data0, h, moeda):
    """Preço na data mais próxima de data0+h (±TOL), na mesma moeda. None se ainda não maturou."""
    cands = [(abs(scoring.dias_entre(data0, d) - h), d, p) for d, p, m in sr
             if m == moeda and abs(scoring.dias_entre(data0, d) - h) <= TOL and scoring.dias_entre(data0, d) > 0]
    if not cands: return None, None
    _, d, p = min(cands, key=lambda x: x[0])
    return p, d

def _mensal(previsoes):
    """Uma previsão por item por mês — a primeira de cada mês."""
    vistos, out = set(), []
    for p in previsoes:
        k = (p["item_id"], p["data"][:7])
        if k in vistos: continue
        vistos.add(k); out.append(p)
    return out

def _acertou(veredito, r):
    if veredito == "Comprar": return r > 0
    if veredito == "Evitar":  return r <= 0
    return None                                   # "Acompanhar" não é uma aposta direcional

def _stats(rs):
    if not rs: return {"n": 0, "media": None, "mediana": None}
    return {"n": len(rs), "media": round(st.mean(rs), 1), "mediana": round(st.median(rs), 1)}

def correr(previsoes_todas, series_por_item, nomes):
    """previsoes_todas: lista de dicts da tabela previsoes.
    series_por_item: {item_id: [(data, preco, moeda)]} — scoring.serie() dos snapshots."""
    casos, resumo = [], []
    base = _mensal([p for p in previsoes_todas if p["veredito"] in AVALIAVEIS and p["preco_ref"]])
    for h in HORIZONTES:
        rs_universo, por_v = [], {}
        for p in base:
            sr = series_por_item.get(p["item_id"]) or []
            pf, df = _preco_no_horizonte(sr, p["data"], h, p["moeda"])
            if pf is None: continue
            r = (pf - p["preco_ref"]) / p["preco_ref"] * 100
            rs_universo.append(r)
            por_v.setdefault(p["veredito"], []).append(r)
            casos.append({"item_id": p["item_id"], "nome": nomes.get(p["item_id"], p["item_id"]),
                          "data": p["data"], "horizonte": h, "veredito": p["veredito"], "score": p["score"],
                          "precoRef": round(p["preco_ref"], 2), "precoFim": round(pf, 2), "dataFim": df,
                          "moeda": p["moeda"], "retorno": round(r, 1), "acertou": _acertou(p["veredito"], r)})
        u = _stats(rs_universo)
        vereditos = {}
        for v, rs in por_v.items():
            d = _stats(rs)
            certos = [x for x in (_acertou(v, r) for r in rs) if x is not None]
            d["acerto"] = round(100 * sum(certos) / len(certos)) if certos else None
            d["vantagem"] = round(d["media"] - u["media"], 1) if (d["media"] is not None and u["media"] is not None) else None
            vereditos[v] = d
        resumo.append({"horizonte": h, "universo": u, "vereditos": vereditos})

    # previsões ainda a maturar: quantas e quando dá para avaliar a primeira
    hoje = dt.date.today().isoformat()
    pend = [p for p in base if scoring.dias_entre(p["data"], hoje) < HORIZONTES[0] - TOL]
    falta = min((HORIZONTES[0] - TOL - scoring.dias_entre(p["data"], hoje) for p in pend), default=None)
    casos.sort(key=lambda c: (c["data"], c["horizonte"]), reverse=True)
    return {"horizontes": list(HORIZONTES), "amostragem": "mensal", "tolerancia": TOL,
            "resumo": resumo, "casos": casos[:200],
            "pendentes": {"n": len(pend), "diasParaPrimeira": falta},
            "totalPrevisoes": len(previsoes_todas)}
