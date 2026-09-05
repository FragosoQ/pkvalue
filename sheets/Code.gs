/** PokéValor — API Google Sheets (Apps Script)
 *  Implementar como Web app: Executar como "Eu", acesso "Qualquer pessoa".
 *  GET  ?tipo=itens|obs|compras|tudo[&token=...]
 *  POST body JSON {acao, token, ...}   (enviar como text/plain para evitar preflight CORS)
 */
const SHEET_ID = '1FY97k3TtH4Axd6gy97GYthxArLg0qgmxzHD2BHrbCws';
const TOKEN    = '';   // opcional: define uma palavra-passe e usa-a na app e no job
const ABAS = { itens: ['Folha1', 'Itens'], obs: ['Observacoes'], compras: ['Compras'] };
const COLS = {
  itens:   ['id','nome','tipo','set','ano','lang','img','producao','ultima_reimpressao','tipo_set','pop_psa10','esc_override','proc','links','notas','termo_pesquisa','poketrace_id','ppt_tcgplayer_id','criado','atualizado','origem'],
  obs:     ['id','item_id','data','fonte','tier','preco','moeda','mercado','vendas','avg30d','origem'],
  compras: ['id','item_id','data','qtd','preco','estado','local','notas']
};

function aba_(k){ const ss=SpreadsheetApp.openById(SHEET_ID); for (const n of ABAS[k]) { const s=ss.getSheetByName(n); if (s) return s; } throw new Error('Separador em falta: '+ABAS[k][0]); }
function ler_(k){
  const s=aba_(k), v=s.getDataRange().getValues(); if (v.length<2) return [];
  const h=v[0].map(String); return v.slice(1).filter(r=>r[0]!=='').map(r=>{ const o={}; h.forEach((c,i)=>o[c]=norm_(r[i])); return o; });
}
function norm_(x){ if (x instanceof Date) return Utilities.formatDate(x,'Europe/Lisbon','yyyy-MM-dd'); return x===''?null:x; }
function linha_(k,o){ return COLS[k].map(c=>{ let v=o[c]; if (v==null) return ''; if (Array.isArray(v)) return v.join(';'); return v; }); }
function idx_(s){ const ids=s.getRange(2,1,Math.max(s.getLastRow()-1,1),1).getValues().map(r=>String(r[0])); return id=>{ const i=ids.indexOf(String(id)); return i<0?-1:i+2; }; }

function doGet(e){
  const p=e.parameter||{}; if (TOKEN && p.token!==TOKEN) return json_({erro:'token'});
  const t=p.tipo||'tudo';
  const out = t==='tudo' ? {itens:ler_('itens'),obs:ler_('obs'),compras:ler_('compras')} : {[t]:ler_(t)};
  return json_(out);
}

function doPost(e){
  const b=JSON.parse(e.postData.contents||'{}'); if (TOKEN && b.token!==TOKEN) return json_({erro:'token'});
  const lock=LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const hoje=Utilities.formatDate(new Date(),'Europe/Lisbon','yyyy-MM-dd');
    switch (b.acao) {
      case 'upsert_item': {
        const s=aba_('itens'), f=idx_(s)(b.item.id), it={...b.item, atualizado:hoje};
        if (f<0){ it.criado=hoje; s.appendRow(linha_('itens',it)); }
        else { const cur=s.getRange(f,1,1,COLS.itens.length).getValues()[0]; it.criado=cur[COLS.itens.indexOf('criado')]||hoje; s.getRange(f,1,1,COLS.itens.length).setValues([linha_('itens',it)]); }
        if (b.obs && b.obs.length) addObs_(b.item.id, b.obs, 'manual');
        return json_({ok:true});
      }
      case 'add_obs':      addObs_(b.item_id, b.obs, b.origem||'manual'); return json_({ok:true});
      case 'add_obs_bulk': (b.lista||[]).forEach(x=>addObs_(x.item_id,[x],x.origem||'auto')); return json_({ok:true});
      case 'del_obs': { const s=aba_('obs'), f=idx_(s)(b.id); if (f>0) s.deleteRow(f); return json_({ok:true}); }
      case 'del_item': {
        const s=aba_('itens'), f=idx_(s)(b.id); if (f>0) s.deleteRow(f);
        ['obs','compras'].forEach(k=>{ const sh=aba_(k), v=sh.getDataRange().getValues(); for (let i=v.length-1;i>=1;i--) if (String(v[i][1])===String(b.id)) sh.deleteRow(i+1); });
        return json_({ok:true});
      }
      case 'add_compra': { const s=aba_('compras'); s.appendRow(linha_('compras',b.compra)); return json_({ok:true}); }
      case 'del_compra': { const s=aba_('compras'), f=idx_(s)(b.id); if (f>0) s.deleteRow(f); return json_({ok:true}); }
      default: return json_({erro:'acao desconhecida'});
    }
  } finally { lock.releaseLock(); }
}

function addObs_(itemId, lista, origem){
  const s=aba_('obs'), ex=ler_('obs').map(o=>[o.item_id,o.data,o.fonte,Number(o.preco)].join('|'));
  const rows=[];
  lista.forEach(o=>{ const k=[itemId,o.data,o.fonte,Number(o.preco)].join('|'); if (ex.indexOf(k)>=0 || o.preco==null) return; ex.push(k);
    rows.push(linha_('obs',{id:Utilities.getUuid().slice(0,8), item_id:itemId, data:o.data, fonte:o.fonte, tier:o.tier||'MANUAL', preco:o.preco, moeda:o.moeda||'EUR', mercado:o.mercado||'', vendas:o.vendas||'', avg30d:o.avg30d||'', origem:o.origem||origem})); });
  if (rows.length) s.getRange(s.getLastRow()+1,1,rows.length,COLS.obs.length).setValues(rows);
}

function json_(o){ return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

/** Corre uma vez para criar/validar os cabeçalhos (menu Executar → cabecalhos). */
function cabecalhos(){ Object.keys(COLS).forEach(k=>{ const s=aba_(k); if (s.getLastRow()===0) s.appendRow(COLS[k]); }); }
