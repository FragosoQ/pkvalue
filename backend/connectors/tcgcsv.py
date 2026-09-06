"""TCGCSV — espelho dos preços TCGplayer (tcgcsv.com), a única fonte conhecida que
cobre PRODUTO SELADO (booster box, ETB), que nem o catálogo pokemontcg.io nem o
plano free do PokemonPriceTracker dão.

DESLIGADO POR OMISSÃO (TCGCSV=1 para ligar). Em 2026-09-06 o serviço passou a
responder 401 Unauthorized aos pedidos anónimos, por isso deixou de ser utilizável
sem credenciais. O esquema de autenticação não está aqui documentado porque não foi
possível verificá-lo — se tiveres acesso, liga com TCGCSV=1 e confirma com o
autoteste no fim deste ficheiro.

Categoria 3 = Pokémon. Endpoints usados:
  /tcgplayer/3/groups              -> sets (groupId, name, abbreviation)
  /tcgplayer/3/{groupId}/products  -> produtos do set (productId, name)
  /tcgplayer/3/{groupId}/prices    -> preços (productId, marketPrice, subTypeName)

Tudo aqui é best-effort: qualquer falha levanta e o job apanha, nunca interrompe a recolha.
Verificar à mão:  python -m connectors.tcgcsv "Evolving Skies"
"""
import re, os, time, logging, requests

log = logging.getLogger("tcgcsv")
BASE = "https://tcgcsv.com/tcgplayer/3"
_cache = {}

# Orçamento global. Uma fonte gratuita e opcional nunca pode bloquear a recolha diária:
# são precisos ~27 pedidos (lista de grupos + products/prices por set) e, sem teto, um
# serviço lento multiplicava timeout × tentativas × caminhos até dezenas de minutos.
ORCAMENTO_S = int(os.getenv("TCGCSV_ORCAMENTO_S", "120"))   # tempo total para toda a fase
TIMEOUT_S   = int(os.getenv("TCGCSV_TIMEOUT_S", "15"))      # por pedido
TENTATIVAS  = 2

class Indisponivel(Exception):
    """TCGCSV fora de alcance ou orçamento esgotado — os selados ficam sem preço nesse dia."""

_estado = {"inicio": None, "desligado": None}

def desligado():
    """Motivo por que o TCGCSV foi desligado nesta execução, ou None se ainda está ativo."""
    return _estado["desligado"]

def _restante():
    if _estado["inicio"] is None: _estado["inicio"] = time.monotonic()
    return ORCAMENTO_S - (time.monotonic() - _estado["inicio"])

def _get(path):
    if path in _cache: return _cache[path]
    if _estado["desligado"]: raise Indisponivel(_estado["desligado"])
    ult, servico = None, False
    for tent in range(TENTATIVAS):
        se_falta = _restante()
        if se_falta <= 0:
            _estado["desligado"] = f"orçamento de {ORCAMENTO_S}s esgotado"
            raise Indisponivel(_estado["desligado"])
        try:
            r = requests.get(f"{BASE}{path}", timeout=min(TIMEOUT_S, max(1, se_falta)))
            r.raise_for_status()
            d = r.json()
            res = d.get("results", d if isinstance(d, list) else [])
            _cache[path] = res
            return res
        except (requests.Timeout, requests.ConnectionError) as e:
            ult, servico = e, True
            if tent + 1 < TENTATIVAS: time.sleep(1)
        except requests.HTTPError as e:
            ult = e
            # 401/403 (precisa de credenciais), 429 (limite) e 5xx são condições do SERVIÇO:
            # repetir nos outros 26 caminhos só produz o mesmo erro. 404 é só deste caminho.
            servico = (e.response is not None and e.response.status_code in (401, 403, 429) or
                       e.response is not None and e.response.status_code >= 500)
            break
        except Exception as e:
            ult, servico = e, False    # JSON inválido: deste caminho
            break
    if servico:
        _estado["desligado"] = f"{ult}"
        raise Indisponivel(_estado["desligado"])
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
    """Linha normalizada, no mesmo formato dos outros conectores. None se não houver.
    Levanta Indisponivel se o serviço estiver fora de alcance ou o orçamento esgotado."""
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
