"""API local para a app HTML. Executar: uvicorn api:app --reload --port 8000"""
import json, uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import db, job
from config import CAPS

app = FastAPI(title="PokéValor API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Item(BaseModel):
    id: str | None = None; nome: str; tipo: str; set: str | None = ""; ano: int | None = None
    lang: str = "Inglês"; esc: int = 3; proc: int = 3; links: list[str] = []; notas: str = ""
    producao: str | None = None; ultima_reimpressao: str | None = None; tipo_set: str | None = None; pop_psa10: int | None = None; esc_override: int | None = None
    termo_pesquisa: str | None = None; poketrace_id: str | None = None; ppt_tcgplayer_id: str | None = None; ppt_sealed_id: str | None = None

class Compra(BaseModel):
    id: str | None = None; itemId: str; data: str; qtd: int = 1; preco: float; estado: str = "Selado"; local: str = ""

@app.get("/capacidades")
def capacidades(): return CAPS

@app.get("/dados")
def dados():
    c = db.conn(); d = job.exporta(c); c.commit(); return d

@app.post("/itens")
def cria_item(i: Item):
    c = db.conn(); iid = i.id or uuid.uuid4().hex[:8]
    c.execute("""INSERT OR REPLACE INTO itens(id,nome,tipo,set_nome,ano,lang,esc,proc,links,notas,termo_pesquisa,poketrace_id,ppt_tcgplayer_id,ppt_sealed_id,producao,ultima_reimpressao,tipo_set,pop_psa10,esc_override)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (iid, i.nome, i.tipo, i.set, i.ano, i.lang, i.esc, i.proc, json.dumps(i.links), i.notas, i.termo_pesquisa, i.poketrace_id, i.ppt_tcgplayer_id, i.ppt_sealed_id,
               i.producao, i.ultima_reimpressao, i.tipo_set, i.pop_psa10, i.esc_override))
    c.commit(); return {"id": iid}

@app.post("/itens/importar")
def importa(payload: dict):
    """Recebe o JSON exportado pela app (itens + compras) e carrega tudo na BD."""
    c = db.conn(); n = 0
    for i in payload.get("itens", []):
        cria_item(Item(**{k: i.get(k) for k in Item.model_fields if k in i})); n += 1
    for k in payload.get("compras", []): cria_compra(Compra(**k))
    return {"importados": n}

@app.delete("/itens/{iid}")
def apaga_item(iid: str):
    c = db.conn(); c.execute("DELETE FROM itens WHERE id=?", (iid,)); c.execute("DELETE FROM snapshots WHERE item_id=?", (iid,))
    c.execute("DELETE FROM compras WHERE item_id=?", (iid,)); c.commit(); return {"ok": True}

@app.post("/compras")
def cria_compra(k: Compra):
    c = db.conn(); cid = k.id or uuid.uuid4().hex[:8]
    c.execute("INSERT OR REPLACE INTO compras VALUES(?,?,?,?,?,?,?)", (cid, k.itemId, k.data, k.qtd, k.preco, k.estado, k.local))
    c.commit(); return {"id": cid}

@app.post("/observacao")
def obs_manual(item_id: str, preco: float, fonte: str = "manual", data: str | None = None):
    """Para selado no plano free: regista o preço visto no eBay/Cardmarket."""
    c = db.conn(); db.guarda_snapshot(c, item_id, "manual:" + fonte, "MANUAL", preco, moeda="EUR"); c.commit(); return {"ok": True}

@app.post("/executar")
def executar():
    job.main(); return {"ok": True}
