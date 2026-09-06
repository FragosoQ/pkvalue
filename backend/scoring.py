"""Mesma fórmula da app HTML — mantida aqui como fonte de verdade.

Estados possíveis de um item (campo `tendencia_estado`):
  sem_dados     — nunca houve um preço; não se pontua (score None, veredito "Sem dados")
  insuficiente  — há preço mas menos de MIN_DIAS de histórico; veredito "Prematuro"
  avg30d        — sem histórico próprio, mas o fornecedor deu média 30 dias
  ok            — tendência real calculada na janela móvel
"""
import datetime as dt

SELADO = {"Booster box", "Booster pack", "ETB", "Coleção / Tin"}
PREF = ("cardmarket", "ebay", "tcgplayer")
FATOR_MAX = {"tendencia": 30, "escassez": 30, "procura": 20, "idade": 10, "tipo": 10}
SUB_MAX = {"producao": 10, "reimpressao": 8, "tipo_set": 5, "populacao": 5, "racio": 2}
ESC_MAX = 30
JANELA_DIAS = 90     # tendência = retorno dos últimos 90 dias, não desde sempre
MIN_DIAS = 21        # abaixo disto qualquer variação é ruído

def dias_entre(a, b):
    try: return (dt.date.fromisoformat(b[:10]) - dt.date.fromisoformat(a[:10])).days
    except Exception: return 0

def serie(snaps, preferir=PREF):
    """Um preço de referência por data, sempre da fonte mais prioritária disponível nesse dia.
    Devolve [(data, preco, moeda)] ordenado. Evita saltar entre fontes de dia para dia."""
    por_data = {}
    for s in snaps or []:
        if s.get("preco") is None: continue
        por_data.setdefault(s["data"], []).append(s)
    out = []
    for d in sorted(por_data):
        dia = por_data[d]; esc = None
        for f in preferir:
            for s in dia:
                # fonte vem prefixada pela origem: "descoberta:cardmarket", "poketrace:ebay", "manual:Cardmarket"
                if (s.get("fonte") or "").split(":")[-1].strip().lower().startswith(f):
                    esc = s; break
            if esc: break
        esc = esc or dia[0]
        out.append((d, esc["preco"], esc.get("moeda") or "EUR"))
    return out

def tendencia(snaps, janela=JANELA_DIAS):
    """Retorno % na janela móvel. Devolve (valor, estado)."""
    sr = serie(snaps)
    if not sr: return None, "sem_dados"
    # Nunca comparar EUR com USD. Se as fontes trocam de moeda ao longo do tempo, usa-se a moeda
    # com o histórico mais longo — não a da última observação, que pode ser um ponto solto.
    moedas = []
    for m in {x[2] for x in sr}:
        sub = [x for x in sr if x[2] == m]
        moedas.append((dias_entre(sub[0][0], sub[-1][0]), sub[-1][0], sub))
    moedas.sort(key=lambda c: (c[0], c[1]), reverse=True)
    mesma = moedas[0][2]
    d_ult, p_ult, _ = mesma[-1]
    base = None
    for d, p, _ in mesma[:-1]:
        if dias_entre(d, d_ult) >= janela: base = (d, p)  # a mais recente já com a janela completa
    if base is None:
        antigos = [x for x in mesma[:-1] if dias_entre(x[0], d_ult) >= MIN_DIAS]
        if antigos: base = (antigos[0][0], antigos[0][1])  # ainda não há 90 dias: usa o mais antigo utilizável
    if base and base[1]:
        return (p_ult - base[1]) / base[1] * 100, "ok"
    for s in reversed(snaps):                              # sem histórico próprio: média 30d do fornecedor
        if s.get("avg30d") and s.get("preco") is not None:
            return (s["preco"] - s["avg30d"]) / s["avg30d"] * 100, "avg30d"
    return None, "insuficiente"

def preco_atual(snaps, preferir=PREF):
    sr = serie(snaps, preferir)
    return (sr[-1][1], sr[-1][2]) if sr else (None, None)

def meses_desde(iso):
    if not iso: return None
    try:
        y, m = int(iso[:4]), int(iso[5:7]) if len(iso) >= 7 else 1
        h = dt.date.today(); return (h.year - y) * 12 + (h.month - m)
    except Exception: return None

def escassez(item, snaps):
    """0–30. Só contam os sub-fatores APLICÁVEIS a este tipo de item e com DADOS.
    O total é normalizado sobre o máximo do que foi possível avaliar.

    Antes, um sub-fator desconhecido recebia um valor neutro (população 2/5,
    rácio 1/2) que contava contra o denominador cheio de 30 — inventava
    informação e penalizava quem tem menos dados. E a população PSA 10 é um
    indicador de cartas: aplicada a produto selado não significa nada.

    Se esc_override (1–5) estiver definido, manda ele: esc_override*6."""
    if item.get("esc_override"): return item["esc_override"] * 6, {"override": True}
    selado = item["tipo"] in SELADO
    sub = {}
    sub["producao"] = {"v": {"em": 0, "fim_anunciado": 5, "fora": 10}.get(item.get("producao") or "em", 0), "estado": "ok"}
    m = meses_desde(item.get("ultima_reimpressao") or (f"{item['ano']}-01" if item.get("ano") else None))
    sub["reimpressao"] = {"v": None, "estado": "desconhecido"} if m is None else {"v": min(8, (m // 6) * 2), "estado": "ok"}
    sub["tipo_set"] = {"v": {"principal": 0, "especial": 3, "promo": 5}.get(item.get("tipo_set") or "principal", 0), "estado": "ok"}
    pop = item.get("pop_psa10")
    if selado:
        sub["populacao"] = {"v": None, "estado": "na"}          # PSA gradua cartas, não caixas seladas
    elif pop in (None, ""):
        sub["populacao"] = {"v": None, "estado": "desconhecido"}
    else:
        sub["populacao"] = {"v": 0 if pop > 5000 else 1 if pop > 2000 else 3 if pop > 1000 else 4 if pop > 500 else 5, "estado": "ok"}
    r = racio_vendas_oferta(snaps)
    sub["racio"] = {"v": r, "estado": "ok"} if r is not None else {"v": None, "estado": "desconhecido"}
    for k, d in sub.items(): d["max"] = SUB_MAX[k]
    validos = [d for d in sub.values() if d["estado"] == "ok"]
    base = sum(d["v"] for d in validos); base_max = sum(d["max"] for d in validos)
    total = round(ESC_MAX * base / base_max) if base_max else 0
    return total, {"sub": sub, "base": base, "baseMax": base_max, "total": total}

def racio_vendas_oferta(snaps):
    """0–2: vendas recentes vs anúncios ativos. None quando a API não dá ambos —
    antes devolvia 1 ("neutro"), que era um palpite disfarçado de medição."""
    ult = [s for s in snaps if s.get("vendas") and s.get("raw")] if snaps else []
    for s in reversed(ult):
        try:
            import json; r = json.loads(s["raw"]) if isinstance(s["raw"], str) else s["raw"]
            listings = r.get("listings") or r.get("sellers")
            if listings: q = s["vendas"] / listings; return 2 if q > 1.0 else 1 if q > 0.4 else 0
        except Exception: pass
    return None

def score(item, snaps):
    """Devolve (score 0–100, detalhe).

    O score é normalizado sobre os fatores REALMENTE avaliáveis, tal como a escassez.
    Antes, um item sem qualquer preço não era pontuado de todo — mas a tendência é só
    30 dos 100 pontos: escassez, procura, idade e tipo (70 pontos) não dependem de
    preço nenhum e podem ser avaliados desde o primeiro dia.

    `confianca` diz sobre quantos dos 100 pontos a avaliação foi feita, para que
    56/100 com confiança 70 não se confunda com 56/100 com confiança 100."""
    t, estado = tendencia(snaps)
    p_e, det_e = escassez(item, snaps)
    idade = dt.date.today().year - (item["ano"] or dt.date.today().year)
    f = {}
    # A tendência só entra quando existe de facto — não se atribui um valor neutro.
    f["tendencia"] = ({"v": max(0, min(30, 15 + t / 2)), "estado": "ok"} if t is not None
                      else {"v": None, "estado": "desconhecido"})
    f["escassez"] = ({"v": p_e, "estado": "ok"} if (det_e.get("override") or det_e.get("baseMax"))
                     else {"v": None, "estado": "desconhecido"})
    f["procura"] = {"v": item["proc"] * 4, "estado": "ok"}
    f["idade"] = ({"v": min(10, idade * 2), "estado": "ok"} if item.get("ano")
                  else {"v": None, "estado": "desconhecido"})
    f["tipo"] = {"v": 10 if item["tipo"] in SELADO else (7 if item["tipo"] == "Set completo" else 5), "estado": "ok"}
    for k, d in f.items(): d["max"] = FATOR_MAX[k]
    ok = [d for d in f.values() if d["estado"] == "ok"]
    base = sum(d["v"] for d in ok); base_max = sum(d["max"] for d in ok)
    s = round(100 * base / base_max) if base_max else None
    return s, {"tendencia": t, "tendencia_estado": estado, "fatores": f,
               "base": base, "baseMax": base_max, "confianca": base_max,
               "pontos": {k: (d["v"] or 0) for k, d in f.items()},
               "escassez": det_e}

def veredito(s, estado="ok"):
    """O veredito lê-se sempre com a confiança ao lado: um "Comprar" avaliado sobre
    70 pontos é uma leitura sem sinal de mercado, não uma certeza."""
    if s is None: return "Sem dados"
    return "Comprar" if s >= 70 else ("Acompanhar" if s >= 50 else "Evitar")
