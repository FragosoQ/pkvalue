"""Descoberta automática de candidatos: sets recentes → booster box, ETB e cartas mais caras.
Fonte gratuita, sem chave: api.pokemontcg.io (catálogo + preços Cardmarket/TCGplayer)."""
import json, datetime as dt, logging, requests, os
import db
from config import DESCOBERTA_MESES, DESCOBERTA_TOP, POKEMONTCG_KEY
log = logging.getLogger("descoberta")
BASE = "https://api.pokemontcg.io/v2"
H = {"X-Api-Key": POKEMONTCG_KEY} if POKEMONTCG_KEY else {}
ESPECIAIS = ("151", "celebrations", "crown zenith", "shining fates", "hidden fates", "champion's path", "pokemon go", "prismatic", "shrouded", "paldean fates", "destined", "anniversary")
import re as _re
ESPECIAIS_RE = _re.compile("|".join(_re.escape(x) for x in ESPECIAIS), _re.I)

import time
def _get(path, **p):
    for tent in range(3):
        try:
            r = requests.get(f"{BASE}{path}", params=p, headers=H, timeout=90); r.raise_for_status(); return r.json().get("data", [])
        except Exception as e:
            if tent == 2: raise
            time.sleep(3 * (tent + 1))

def sets_recentes():
    lim = (dt.date.today() - dt.timedelta(days=30 * DESCOBERTA_MESES)).strftime("%Y/%m/%d")
    todos = _get("/sets", orderBy="-releaseDate", pageSize=250)          # sem filtro na query (o servidor devolve 500 com releaseDate>=)
    return [s for s in todos if (s.get("releaseDate") or "0000/00/00") >= lim]

def cartas_top(set_id):
    return _get("/cards", q=f"set.id:{set_id}", orderBy="-cardmarket.prices.trendPrice", pageSize=DESCOBERTA_TOP, select="id,name,number,rarity,images,cardmarket,tcgplayer,set")

def _upsert(c, it):
    """Cria o candidato se não existir; se já existir (teu ou descoberto) não mexe nos teus campos."""
    ex = c.execute("SELECT id FROM itens WHERE id=?", (it["id"],)).fetchone()
    if ex: return False
    # campos_auto marca os campos como preenchidos automaticamente, para o enriquecimento
    # os poder atualizar depois (sobretudo `producao`, que envelhece com o set)
    c.execute("""INSERT INTO itens(id,nome,tipo,set_nome,ano,lang,esc,proc,links,notas,termo_pesquisa,producao,tipo_set,img,origem,campos_auto)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'descoberta',?)""",
              (it["id"], it["nome"], it["tipo"], it["set"], it["ano"], "Inglês", 3, it.get("proc", 3), "[]", it.get("notas", ""),
               it.get("termo"), "em", it["tipo_set"], it.get("img"),
               json.dumps(["set_nome", "ano", "tipo_set", "img", "producao"])))
    return True

def correr(c):
    novos = 0; precos = 0
    try: sets = sets_recentes()
    except Exception as e: log.warning("pokemontcg.io sets: %s", e); return 0
    for s in sets:
        ano = int(s["releaseDate"][:4]); nome = s["name"]; sid = s["id"]
        tipo_set = "especial" if any(k in nome.lower() for k in ESPECIAIS) or (s.get("printedTotal") or 999) < 120 else "principal"
        base = dict(set=nome, ano=ano, tipo_set=tipo_set, img=(s.get("images") or {}).get("logo"))
        novos += _upsert(c, {**base, "id": f"d-{sid}-box", "nome": f"{nome} booster box", "tipo": "Booster box", "proc": 4, "termo": f"{nome} booster box"})
        novos += _upsert(c, {**base, "id": f"d-{sid}-etb", "nome": f"{nome} Elite Trainer Box", "tipo": "ETB", "proc": 3, "termo": f"{nome} elite trainer box"})
        try: cartas = cartas_top(sid)
        except Exception as e: log.warning("cartas %s: %s", sid, e); cartas = []
        for k in cartas:
            cid = f"d-{k['id']}"; num = f"{k['number']}/{s.get('printedTotal') or ''}"
            _upsert(c, {**base, "id": cid, "nome": f"{k['name']} {num}", "tipo": "Carta", "proc": 4, "img": k["images"]["large"],
                        "notas": k.get("rarity") or "", "termo": f"{k['name']} {num}"}) and (novos := novos + 1)
            cm = ((k.get("cardmarket") or {}).get("prices") or {}).get("trendPrice")
            tp = next(iter(((k.get("tcgplayer") or {}).get("prices") or {}).values()), {}).get("market")
            if cm: db.guarda_snapshot(c, cid, "descoberta:cardmarket", "TREND", cm, moeda="EUR", mercado="EU", raw={"avg30": ((k.get("cardmarket") or {}).get("prices") or {}).get("avg30")}); precos += 1
            elif tp: db.guarda_snapshot(c, cid, "descoberta:tcgplayer", "MARKET", tp, moeda="USD", mercado="US", raw={}); precos += 1
        c.commit()
    log.info("Descoberta: %d sets, %d candidatos novos, %d preços", len(sets), novos, precos)
    return novos
