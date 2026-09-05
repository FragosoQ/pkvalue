import sqlite3, json, datetime as dt
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS itens (
  id TEXT PRIMARY KEY, nome TEXT NOT NULL, tipo TEXT NOT NULL, set_nome TEXT, ano INTEGER,
  lang TEXT DEFAULT 'Inglês', esc INTEGER DEFAULT 3, proc INTEGER DEFAULT 3,
  links TEXT DEFAULT '[]', notas TEXT DEFAULT '',
  poketrace_id TEXT, ppt_tcgplayer_id TEXT, ppt_sealed_id TEXT, termo_pesquisa TEXT,
  criado TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS snapshots (        -- histórico próprio: cresce todos os dias, sem limite do fornecedor
  id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL, data TEXT NOT NULL,
  fonte TEXT NOT NULL, mercado TEXT, moeda TEXT, tier TEXT,
  preco REAL, preco_low REAL, preco_high REAL, vendas INTEGER, avg7d REAL, avg30d REAL,
  raw TEXT, UNIQUE(item_id, data, fonte, tier)
);
CREATE TABLE IF NOT EXISTS compras (
  id TEXT PRIMARY KEY, item_id TEXT NOT NULL, data TEXT, qtd INTEGER DEFAULT 1,
  preco REAL, estado TEXT, local TEXT
);
CREATE TABLE IF NOT EXISTS uso_api (fornecedor TEXT, data TEXT, chamadas INTEGER, PRIMARY KEY(fornecedor,data));
"""

NOVAS = [("producao","TEXT"),("ultima_reimpressao","TEXT"),("tipo_set","TEXT"),("pop_psa10","INTEGER"),("esc_override","INTEGER"),("img","TEXT")]
def conn():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    cols = {r["name"] for r in c.execute("PRAGMA table_info(itens)")}
    for n, t in NOVAS:
        if n not in cols: c.execute(f"ALTER TABLE itens ADD COLUMN {n} {t}")
    return c

def hoje(): return dt.date.today().isoformat()

def uso(c, fornecedor):
    r = c.execute("SELECT chamadas FROM uso_api WHERE fornecedor=? AND data=?", (fornecedor, hoje())).fetchone()
    return r["chamadas"] if r else 0

def regista_uso(c, fornecedor, n=1):
    c.execute("INSERT INTO uso_api VALUES(?,?,?) ON CONFLICT(fornecedor,data) DO UPDATE SET chamadas=chamadas+?", (fornecedor, hoje(), n, n))

def guarda_snapshot(c, item_id, fonte, tier, preco, **k):
    c.execute("""INSERT OR REPLACE INTO snapshots(item_id,data,fonte,mercado,moeda,tier,preco,preco_low,preco_high,vendas,avg7d,avg30d,raw)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (item_id, hoje(), fonte, k.get("mercado"), k.get("moeda"), tier, preco, k.get("low"), k.get("high"),
               k.get("vendas"), k.get("avg7d"), k.get("avg30d"), json.dumps(k.get("raw", {}))[:4000]))

def itens(c): return [dict(r) for r in c.execute("SELECT * FROM itens").fetchall()]
def snapshots(c, item_id):
    return [dict(r) for r in c.execute("SELECT * FROM snapshots WHERE item_id=? ORDER BY data", (item_id,)).fetchall()]
def compras(c): return [dict(r) for r in c.execute("SELECT * FROM compras").fetchall()]
