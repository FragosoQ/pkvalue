"""Preenche automaticamente, a partir do catálogo pokemontcg.io, os campos que ficariam
por omissão — e que sem isso deixam a escassez a correr às cegas.

Regras que este módulo respeita sempre:
  1. NUNCA sobrepõe um valor que tenhas definido. Só preenche campos vazios, ou campos
     que ele próprio preencheu antes (registados em `campos_auto`).
  2. O estado de produção é INFERIDO da idade do set, não medido. Fica marcado como tal
     para poderes corrigir — e uma correção tua passa a ser respeitada para sempre.
"""
import json, logging, re, datetime as dt
import db, descoberta

log = logging.getLogger("enriquecer")

# Um set fica em impressão ~1 a 2 anos. É uma aproximação, não um facto:
# por isso o campo fica marcado como inferido e é sobreponível.
JANELAS = ((12, "em"), (24, "fim_anunciado"), (10**6, "fora"))

def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"\b(pok[eé]mon|tcg|sword\s*&?\s*shield|scarlet\s*&?\s*violet|sun\s*&?\s*moon|xy|swsh|sv)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

_SETS = None
def sets_todos():
    global _SETS
    if _SETS is None:
        _SETS = descoberta._get("/sets", orderBy="-releaseDate", pageSize=250) or []
    return _SETS

def acha_set(nome_set, nome_item):
    """Correspondência exata ou contida. Sem palpites vagos: mais vale não enriquecer
    do que colar a um set errado e produzir uma pontuação com base noutro produto."""
    for alvo in (_norm(nome_set), _norm(nome_item)):
        if not alvo: continue
        exato, parcial = [], []
        for st in sets_todos():
            n = _norm(st.get("name"))
            if not n: continue
            if n == alvo: exato.append(st)
            elif len(n) >= 5 and n in alvo: parcial.append(st)
        if exato: return exato[0]
        if len(parcial) == 1: return parcial[0]
        if parcial: return max(parcial, key=lambda s: len(_norm(s.get("name"))))
    return None

def meses_desde(iso):
    try:
        d = dt.date(int(iso[:4]), int(iso[5:7]), 1); h = dt.date.today()
        return (h.year - d.year) * 12 + (h.month - d.month)
    except Exception: return None

def producao_inferida(release):
    m = meses_desde((release or "").replace("/", "-"))
    if m is None: return None
    for lim, val in JANELAS:
        if m < lim: return val

# Campos que a descoberta automática preenche ao criar um candidato. São dela, não teus:
# sem isto, o `producao='em'` gravado no nascimento ficava congelado para sempre e a
# escassez nunca subia quando o set saía de produção.
CAMPOS_DESCOBERTA = ["set_nome", "ano", "tipo_set", "img", "producao"]

def enriquece(c, it):
    """Devolve a lista de campos preenchidos nesta passagem."""
    auto = set(json.loads(it.get("campos_auto") or "[]"))
    if not auto and (it.get("origem") or "") == "descoberta":
        auto = set(CAMPOS_DESCOBERTA)
    st = acha_set(it.get("set_nome"), it.get("nome"))
    if not st: return []
    rel = (st.get("releaseDate") or "").replace("/", "-")
    novos, vals = [], {}
    def por(campo, valor):
        if valor in (None, ""): return
        atual = it.get(campo)
        # preenche se está vazio, ou se fomos nós a pôr lá o valor anterior
        if atual in (None, "", 0) or campo in auto:
            if atual != valor: vals[campo] = valor; novos.append(campo)
            auto.add(campo)
    por("set_nome", st.get("name"))
    por("ano", int(rel[:4]) if rel[:4].isdigit() else None)
    por("tipo_set", "especial" if (descoberta.ESPECIAIS_RE.search(st.get("name") or "") or (st.get("printedTotal") or 999) < 120) else "principal")
    if it["tipo"] in ("Booster box", "ETB", "Booster pack", "Coleção / Tin"):
        por("img", (st.get("images") or {}).get("logo"))
    por("producao", producao_inferida(rel))
    if not vals: return []
    vals["campos_auto"] = json.dumps(sorted(auto))
    c.execute(f"UPDATE itens SET {','.join(k+'=?' for k in vals)} WHERE id=?", (*vals.values(), it["id"]))
    return novos

def correr(c):
    try: sets_todos()
    except Exception as e:
        log.warning("catálogo indisponível, sem enriquecimento nesta execução: %s", e); return 0
    n = 0
    for it in db.itens(c):
        try:
            if enriquece(c, it): n += 1
        except Exception as e:
            log.warning("enriquecer '%s': %s", it.get("nome"), e)
    c.commit()
    log.info("Enriquecidos %d itens a partir do catálogo", n)
    return n
