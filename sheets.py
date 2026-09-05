"""Google Sheets via Apps Script web app (sheets/Code.gs)."""
import requests, json
from config import SHEETS_URL, SHEETS_TOKEN

def ligado(): return bool(SHEETS_URL)

def tudo():
    r = requests.get(SHEETS_URL, params={"tipo": "tudo", "token": SHEETS_TOKEN}, timeout=60); r.raise_for_status()
    d = r.json();  assert "erro" not in d, d.get("erro");  return d

def add_obs_bulk(lista):
    """lista: [{item_id,data,fonte,tier,preco,moeda,mercado,vendas,avg30d,origem}]"""
    if not lista: return
    r = requests.post(SHEETS_URL, data=json.dumps({"acao": "add_obs_bulk", "token": SHEETS_TOKEN, "lista": lista}),
                      headers={"Content-Type": "text/plain"}, timeout=120)
    r.raise_for_status(); d = r.json(); assert "erro" not in d, d.get("erro")
