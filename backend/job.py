"""Job diário: recolhe preços → guarda snapshots → recalcula pontuação → escreve dados.json para a app.
Executar: python job.py   (agendar com cron: 0 7 * * * cd /caminho/backend && python job.py)"""
import json, logging, sys
import db, scoring
from config import CAPS, BUDGET_POKETRACE, BUDGET_PPT, OUTPUT_JSON, ITENS_JSON, POKETRACE_KEY, PPT_KEY, DESCOBERTA, TCGCSV
import descoberta, avaliacao
import os
from connectors import poketrace, ppt, sheets, tcgcsv

log = logging.getLogger("job"); logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

import re
def numero_de(it):
    """Extrai número/total do termo_pesquisa ou do nome: '215/203' -> ('215','203')."""
    m = re.search(r"(\d{1,3})\s*/\s*(\d{2,3})", (it.get("termo_pesquisa") or "") + " " + (it.get("nome") or ""))
    return (m.group(1), m.group(2)) if m else (None, None)

def _campos(obj, pref=""):
    """Achata o JSON em {caminho: valor} para procurar número/total sem depender do nome exacto do campo."""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items(): out.update(_campos(v, f"{pref}{k}."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:5]): out.update(_campos(v, f"{pref}{i}."))
    else: out[pref[:-1]] = obj
    return out

def numeros_da_carta(card):
    """Devolve (números possíveis, totais possíveis) lidos de qualquer campo cujo nome sugira número de carta / total do set."""
    nums, tots = set(), set()
    for k, v in _campos(card).items():
        kl = k.lower().rsplit(".", 1)[-1]
        if v is None: continue
        sv = str(v).strip()
        if kl in ("number", "cardnumber", "card_number", "num", "collectornumber", "collector_number"):
            m = re.match(r"^0*(\d+)\s*(?:/\s*(\d+))?", sv)
            if m: nums.add(m.group(1)); m.group(2) and tots.add(m.group(2))
        elif kl in ("printedtotal", "printed_total", "settotal", "set_total", "total"):
            if sv.isdigit(): tots.add(sv.lstrip("0"))
    return nums, tots

def bate(card, num, total, nome):
    """Aceita a carta se o número coincidir (e o total do set, quando ambos conhecidos); sem número, exige o nome."""
    if num:
        nums, tots = numeros_da_carta(card)
        if num.lstrip("0") not in nums: return False
        if total and tots and total.lstrip("0") not in tots: return False
        return True
    primeira = (nome or "").split()[0].lower()
    return bool(primeira) and primeira in str(card.get("name", "")).lower()

def termo_api(it):
    """Texto de pesquisa limpo: sem número e sem palavras decorativas que confundem a pesquisa."""
    t = it.get("termo_pesquisa") or it.get("nome") or ""
    t = re.sub(r"\d{1,3}\s*/\s*\d{2,3}", " ", t)
    t = re.sub(r"\b(alt(ernate)?\s*art|full\s*art|secret|rainbow|illustration\s*rare|sir|sar)\b", " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()

def escolhe(lista, it):
    num, total = numero_de(it); nome = termo_api(it)
    for card in lista:
        if bate(card, num, total, nome): return card
    resumo = [(c.get("name"), sorted(numeros_da_carta(c)[0]), sorted(numeros_da_carta(c)[1])) for c in lista[:5]]
    log.warning("'%s': nenhum resultado com número %s/%s — não guardo preço. Devolvidos: %s", it["nome"], num, total, resumo)
    if lista and not any(numeros_da_carta(c)[0] for c in lista[:3]):
        log.info("Chaves do 1º resultado (para ajustar o parser): %s", sorted(_campos(lista[0]).keys())[:40])
    return None

def recolhe_item(c, it):
    feito = False
    # --- TCGCSV: única fonte gratuita para selado; corre antes do resto por não gastar créditos ---
    if TCGCSV and it["tipo"] in scoring.SELADO and it.get("set_nome") and not tcgcsv.desligado():
        try:
            p = tcgcsv.preco(it["set_nome"], it["tipo"])
            if p: db.guarda_snapshot(c, it["id"], "tcgcsv:tcgplayer", p.pop("tier"), p.pop("preco"), **{k: v for k, v in p.items() if k != "fonte"}); feito = True
            else: log.info("TCGCSV: sem produto '%s' para o set '%s'", it["tipo"], it["set_nome"])
        except tcgcsv.Indisponivel as e:
            log.warning("TCGCSV indisponível — os selados ficam sem preço nesta execução: %s", e)
        except Exception as e: log.warning("TCGCSV %s: %s", it["nome"], e)
    if (it.get("origem") or "") == "descoberta": return feito   # resto do preço vem do catálogo; poupa créditos
    # --- PokeTrace: cartas (US grátis; EU se plano permitir) ---
    if POKETRACE_KEY and db.uso(c, "poketrace") < BUDGET_POKETRACE and it["tipo"] == "Carta":
        try:
            card = None
            if it["poketrace_id"]:
                card = poketrace.carta(it["poketrace_id"]); db.regista_uso(c, "poketrace")
            elif it["termo_pesquisa"] or it["nome"]:
                termo = termo_api(it)
                res = poketrace.pesquisar(termo, "EU" if CAPS["poketrace"]["eu_market"] else "US", 20)
                db.regista_uso(c, "poketrace")
                card = escolhe(res, it)
                if card: c.execute("UPDATE itens SET poketrace_id=? WHERE id=?", (card["id"], it["id"]))  # fixa o id só quando bate certo
            for p in poketrace.extrai_precos(card or {}):
                db.guarda_snapshot(c, it["id"], "poketrace:" + p.pop("fonte"), p.pop("tier"), p.pop("preco"), **p); feito = True
        except Exception as e: log.warning("PokeTrace %s: %s", it["nome"], e)
    # --- PokemonPriceTracker: cartas por tcgplayerId, selado se plano permitir ---
    if PPT_KEY and db.uso(c, "ppt") < BUDGET_PPT:
        try:
            if it["tipo"] == "Carta":
                if it["ppt_tcgplayer_id"]: card = ppt.carta_por_tcgplayer(it["ppt_tcgplayer_id"])
                else: card = escolhe(ppt.pesquisar_cartas(termo_api(it), 20), it)
                db.regista_uso(c, "ppt")
                if card and not it["ppt_tcgplayer_id"] and card.get("tcgPlayerId"):
                    c.execute("UPDATE itens SET ppt_tcgplayer_id=? WHERE id=?", (str(card["tcgPlayerId"]), it["id"]))
                for p in ppt.extrai_precos(card or {}):
                    db.guarda_snapshot(c, it["id"], "ppt:" + p.pop("fonte"), p.pop("tier"), p.pop("preco"), **p); feito = True
            elif it["tipo"] in scoring.SELADO and CAPS["ppt"]["sealed"] and it["ppt_sealed_id"]:
                # set_id vem do catálogo /sets; o item guarda "setId|nomeProduto"
                set_id, _, nome_prod = it["ppt_sealed_id"].partition("|")
                for sp in ppt.selados(set_id):
                    if nome_prod.lower() in (sp.get("name") or "").lower():
                        pr = sp.get("prices") or {}
                        if pr.get("market") is not None:
                            db.guarda_snapshot(c, it["id"], "ppt:tcgplayer", "SEALED", pr["market"], mercado="US", moeda="USD", raw=pr); feito = True
                db.regista_uso(c, "ppt")
            elif it["tipo"] in scoring.SELADO and not CAPS["ppt"]["sealed"]:
                log.info("Selado '%s': sem plano pago — mantém observações manuais na app.", it["nome"])
        except Exception as e: log.warning("PPT %s: %s", it["nome"], e)
    return feito

def exporta(c):
    out = {"geradoEm": db.hoje(), "capacidades": CAPS, "itens": [], "compras": db.compras(c)}
    series, nomes = {}, {}
    for it in db.itens(c):
        snaps = db.snapshots(c, it["id"])
        s, det = scoring.score(it, snaps)
        preco, moeda = scoring.preco_atual(snaps)
        vd = scoring.veredito(s, det.get("tendencia_estado") or "ok")
        series[it["id"]] = scoring.serie(snaps); nomes[it["id"]] = it["nome"]
        # registo imutável do que a app disse hoje — é isto que permite avaliar o acerto no futuro
        if preco is not None: db.guarda_previsao(c, it["id"], s, vd, det, preco, moeda)
        out["itens"].append({
            "id": it["id"], "nome": it["nome"], "tipo": it["tipo"], "set": it["set_nome"], "ano": it["ano"], "lang": it["lang"],
            "esc": it["esc"], "proc": it["proc"], "links": json.loads(it["links"] or "[]"), "notas": it["notas"],
            "producao": it["producao"], "ultima_reimpressao": it["ultima_reimpressao"], "tipo_set": it["tipo_set"],
            "pop_psa10": it["pop_psa10"], "esc_override": it["esc_override"], "img": it["img"], "origem": it["origem"] or "manual", "racio": det["escassez"].get("racio", 1),
            "score": s, "veredito": vd, "detalhe": det, "precoAtual": preco, "moeda": moeda,
            "cobertura": "sem_dados" if preco is None else (det.get("tendencia_estado") or "ok"),
            # a app consome "obs" — uma observação por dia com o preço de referência
            "obs": [{"data": d, "fonte": "auto", "preco": scoring.preco_atual([x for x in snaps if x["data"] == d])[0]}
                    for d in sorted({x["data"] for x in snaps})],
        })
    c.commit()
    try:
        out["avaliacao"] = avaliacao.correr(db.previsoes(c), series, nomes)
        r0 = out["avaliacao"]["resumo"][0]
        log.info("Avaliação: %d previsões guardadas, %d avaliáveis a 90 dias, %d ainda a maturar",
                 out["avaliacao"]["totalPrevisoes"], r0["universo"]["n"], out["avaliacao"]["pendentes"]["n"])
    except Exception as e:
        log.warning("Avaliação: %s", e); out["avaliacao"] = None
    sem = sum(1 for i in out["itens"] if i["cobertura"] == "sem_dados")
    if sem: log.info("%d itens sem qualquer preço — ficam como 'Sem dados', não pontuados", sem)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=1)
    log.info("dados.json escrito com %d itens", len(out["itens"]))
    return out

def carrega_itens_json(c):
    """Sincroniza itens.json (fonte de verdade editável) com a BD. Compras também."""
    if not os.path.exists(ITENS_JSON): log.info("itens.json não encontrado em %s", ITENS_JSON); return
    with open(ITENS_JSON, encoding="utf-8") as f: d = json.load(f)
    ids = set()
    for i in d.get("itens", []):
        ids.add(i["id"])
        c.execute("""INSERT INTO itens(id,nome,tipo,set_nome,ano,lang,esc,proc,links,notas,termo_pesquisa,producao,ultima_reimpressao,tipo_set,pop_psa10,esc_override,img)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET nome=excluded.nome,tipo=excluded.tipo,set_nome=excluded.set_nome,ano=excluded.ano,
                     lang=excluded.lang,esc=excluded.esc,proc=excluded.proc,links=excluded.links,notas=excluded.notas,termo_pesquisa=excluded.termo_pesquisa,
                     producao=excluded.producao,ultima_reimpressao=excluded.ultima_reimpressao,tipo_set=excluded.tipo_set,pop_psa10=excluded.pop_psa10,esc_override=excluded.esc_override,img=excluded.img""",
                  (i["id"], i["nome"], i["tipo"], i.get("set",""), i.get("ano"), i.get("lang","Inglês"), i.get("esc",3), i.get("proc",3),
                   json.dumps(i.get("links",[])), i.get("notas",""), i.get("termo_pesquisa"),
                   i.get("producao"), i.get("ultima_reimpressao"), i.get("tipo_set"), i.get("pop_psa10") or None, i.get("esc_override") or None, i.get("img")))
        for o in i.get("obs", []):                       # observações manuais feitas na app
            if o.get("fonte") != "auto" and o.get("preco") is not None:
                c.execute("INSERT OR IGNORE INTO snapshots(item_id,data,fonte,moeda,tier,preco,raw) VALUES(?,?,?,?,?,?,?)",
                          (i["id"], o["data"], "manual:"+o.get("fonte","manual"), "EUR", "MANUAL", o["preco"], "{}"))
    if ids:
        # apagado na app = apagado aqui, mas nunca os candidatos da descoberta: se a descoberta
        # falhar num dia (rede em baixo), apagá-los deixaria snapshots e previsões órfãos.
        # Mesma proteção que carrega_sheets() já fazia.
        c.execute(f"DELETE FROM itens WHERE id NOT IN ({','.join('?'*len(ids))}) AND (origem IS NULL OR origem!='descoberta')", tuple(ids))
    for k in d.get("compras", []):
        c.execute("INSERT OR REPLACE INTO compras VALUES(?,?,?,?,?,?,?)",
                  (k["id"], k["itemId"], k.get("data"), k.get("qtd",1), k.get("preco"), k.get("estado",""), k.get("local","")))
    c.commit(); log.info("itens.json carregado: %d itens", len(ids))

def carrega_sheets(c):
    d = sheets.tudo(); ids=set()
    for i in d.get("itens", []):
        ids.add(str(i["id"]))
        c.execute("""INSERT INTO itens(id,nome,tipo,set_nome,ano,lang,esc,proc,links,notas,termo_pesquisa,producao,ultima_reimpressao,tipo_set,pop_psa10,esc_override,img)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET nome=excluded.nome,tipo=excluded.tipo,set_nome=excluded.set_nome,ano=excluded.ano,lang=excluded.lang,proc=excluded.proc,
                     links=excluded.links,notas=excluded.notas,termo_pesquisa=excluded.termo_pesquisa,producao=excluded.producao,ultima_reimpressao=excluded.ultima_reimpressao,
                     tipo_set=excluded.tipo_set,pop_psa10=excluded.pop_psa10,esc_override=excluded.esc_override,img=excluded.img""",
                  (str(i["id"]), i.get("nome",""), i.get("tipo","Carta"), i.get("set") or "", int(i["ano"]) if i.get("ano") else None, i.get("lang") or "Inglês", 3, int(i.get("proc") or 3),
                   json.dumps([x for x in str(i.get("links") or "").split(";") if x]), i.get("notas") or "", i.get("termo_pesquisa"), i.get("producao"), str(i.get("ultima_reimpressao") or "")[:7] or None,
                   i.get("tipo_set"), int(i["pop_psa10"]) if i.get("pop_psa10") else None, int(i["esc_override"]) if i.get("esc_override") else None, i.get("img")))
        c.execute("UPDATE itens SET origem=? WHERE id=?", (i.get("origem") or "manual", str(i["id"])))
    if ids: c.execute(f"DELETE FROM itens WHERE id NOT IN ({','.join('?'*len(ids))}) AND (origem IS NULL OR origem!='descoberta')", tuple(ids))
    for o in d.get("obs", []):
        c.execute("INSERT OR IGNORE INTO snapshots(item_id,data,fonte,moeda,tier,preco,raw) VALUES(?,?,?,?,?,?,?)",
                  (str(o["item_id"]), str(o["data"])[:10], f"{o.get('origem') or 'manual'}:{o.get('fonte') or ''}", o.get("moeda") or "EUR", o.get("tier") or "MANUAL", float(o["preco"]) if o.get("preco") not in (None,"") else None, "{}"))
    c.execute("DELETE FROM compras")
    for k in d.get("compras", []):
        c.execute("INSERT OR REPLACE INTO compras VALUES(?,?,?,?,?,?,?)", (str(k["id"]), str(k["item_id"]), str(k.get("data") or "")[:10], int(k.get("qtd") or 1), float(k.get("preco") or 0), k.get("estado") or "", k.get("local") or ""))
    c.commit(); log.info("Sheets carregado: %d itens", len(ids))

def envia_sheets(c):
    """Empurra candidatos descobertos que ainda não estão na folha e os snapshots automáticos de hoje."""
    na_folha = {str(i["id"]) for i in sheets.tudo().get("itens", [])}
    novos = [dict(r) for r in c.execute("SELECT * FROM itens WHERE origem='descoberta'").fetchall() if r["id"] not in na_folha]
    for it in novos:
        sheets.upsert_item({"id": it["id"], "nome": it["nome"], "tipo": it["tipo"], "set": it["set_nome"], "ano": it["ano"], "lang": it["lang"], "img": it["img"],
                            "producao": it["producao"], "tipo_set": it["tipo_set"], "proc": it["proc"], "links": "", "notas": it["notas"], "termo_pesquisa": it["termo_pesquisa"], "origem": "descoberta"})
    if novos: log.info("Enviados %d candidatos novos para o Sheets", len(novos))
    rows = c.execute("SELECT item_id,data,fonte,tier,preco,moeda,mercado,vendas,avg30d FROM snapshots WHERE data=? AND fonte NOT LIKE 'manual:%' AND fonte NOT LIKE 'auto:%' AND preco IS NOT NULL", (db.hoje(),)).fetchall()
    lista = [dict(item_id=r["item_id"], data=r["data"], fonte=r["fonte"], tier=r["tier"], preco=r["preco"], moeda=r["moeda"] or "USD", mercado=r["mercado"] or "", vendas=r["vendas"] or "", avg30d=r["avg30d"] or "", origem=r["fonte"].split(":")[0]) for r in rows]
    sheets.add_obs_bulk(lista); log.info("Enviadas %d observações para o Sheets", len(lista))

def main():
    c = db.conn()
    if sheets.ligado(): carrega_sheets(c)
    else: carrega_itens_json(c)
    if DESCOBERTA: descoberta.correr(c)
    its = db.itens(c)
    if not its: log.info("Sem itens na BD. Adiciona via API (POST /itens) ou importa da app."); 
    ok = 0
    for it in its:
        if recolhe_item(c, it): ok += 1
        c.commit()
    log.info("Recolhidos %d/%d itens. Uso hoje — poketrace: %d, ppt: %d", ok, len(its), db.uso(c, "poketrace"), db.uso(c, "ppt"))
    if sheets.ligado():
        try: envia_sheets(c)
        except Exception as e: log.warning("Sheets: %s", e)
    exporta(c); c.commit()

if __name__ == "__main__": main()
