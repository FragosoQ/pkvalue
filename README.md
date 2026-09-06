# PokéValor

App pessoal para avaliar o potencial de valorização de cartas, boosters e coleções Pokémon, registar compras e receber sugestões diárias. Corre inteiramente no GitHub: a interface no GitHub Pages, a recolha de preços no GitHub Actions. Sem servidor, sem custos.

```
Telemóvel/PC  ──abre──▶  GitHub Pages (index.html)  ──lê──▶  dados.json
                                                                 ▲
GitHub Actions (todos os dias 07:00 UTC) ── backend/job.py ──────┘
        │ lê itens.json  │ consulta PokeTrace + PokemonPriceTracker + TCGCSV
        │ guarda preços E previsões em backend/pokevalor.db  │ avalia o acerto das previsões antigas
```

## 1. Instalar (10 minutos)

### 1.1 Criar o repositório
1. No GitHub: **New repository** → nome `pokevalor` → **Public** (necessário para o Pages gratuito) → Create.
2. Carrega todos os ficheiros deste zip (**Add file → Upload files**), mantendo a estrutura de pastas. Confirma que ficam na raiz: `index.html`, `itens.json`, `dados.json`, `manifest.json`, `sw.js`, `icon.svg`, a pasta `backend/` e a pasta `.github/workflows/`.

### 1.2 Ativar o GitHub Pages
**Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main / (root) → Save.**
Passados 1–2 minutos, a app fica em `https://<o-teu-utilizador>.github.io/pokevalor/`.

### 1.3 Obter as chaves gratuitas
| Fornecedor | Onde | O que dá no free |
|---|---|---|
| PokeTrace | https://poketrace.com/dashboard | 250 pedidos/dia, preços US (TCGplayer + vendas eBay) de cartas |
| PokemonPriceTracker | https://www.pokemonpricetracker.com/sign-up | 100 créditos/dia, preço TCGplayer + PSA de cartas |
| TCGCSV | https://tcgcsv.com | preços TCGplayer de **produto selado** — **desligado por omissão**, ver 4e |

### 1.4 Guardar as chaves no GitHub (nunca no código)
**Settings → Secrets and variables → Actions → New repository secret**:
- `POKETRACE_API_KEY` → a chave do PokeTrace
- `PPT_API_KEY` → a chave do PokemonPriceTracker

Podes começar só com uma; o job ignora o fornecedor sem chave.

### 1.5 Dar permissão ao Actions para escrever
**Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**

### 1.6 Primeira recolha
**Actions → "Recolha diária de preços" → Run workflow → Run workflow.** Em 1–2 minutos aparece um commit "Preços de AAAA-MM-DD". A partir daí corre sozinho todos os dias.

## 2. Usar no telemóvel

1. Abre `https://<utilizador>.github.io/pokevalor/` no Chrome (Android) ou Safari (iOS).
2. **Adicionar ao ecrã principal** (menu ⋮ no Chrome; botão Partilhar → "Adicionar ao ecrã principal" no Safari). Fica com ícone e abre em ecrã inteiro.
3. Os itens e compras que criares ficam guardados **no próprio telemóvel** (localStorage). Não precisas de exportar para os manter.

## 3. Digitalizar cartas com a câmara
Botão central **Digitalizar** → foto da carta → a app lê nome e número (ex.: `215/203`) e procura no catálogo pokemontcg.io, mostrando imagem, set, ano e preço de referência (Cardmarket/TCGplayer). Escolhe a carta correta → **Adicionar este item**; o formulário fica pré-preenchido com imagem e primeira observação de preço.

- Sem configuração: OCR local (Tesseract.js) no próprio telemóvel; nada sai do dispositivo.
- Opcional: chave API da Anthropic (campo no ecrã Digitalizar) para leitura por modelo de visão — mais fiável em cartas com brilho, japonesas ou danificadas. A chave fica só no `localStorage` do teu telemóvel; nunca vai para o GitHub.
- Para itens já existentes, **Editar → Procurar imagem** vai buscar a imagem ao catálogo pelo nome/número.

## 4. Fluxo de trabalho diário

### Ver sugestões
Separador **Painel**: itens ordenados por pontuação. Verde ≥ 70 = Comprar; âmbar 50–69 = Acompanhar; vermelho < 50 = Evitar; azul = Prematuro (ainda sem histórico); cinzento = Sem dados (nenhum preço recolhido). O botão **Atualizar preços** lê o `dados.json` mais recente; a app também o faz ao abrir.

### Adicionar um item para análise
**Adicionar item** → nome, tipo, set, ano, escassez (1–5), procura (1–5). Dicas:
- Para cartas, escreve o nome como aparece no mercado: `Umbreon VMAX 215/203 Evolving Skies`. É esse texto que o job usa para encontrar a carta nas APIs.
- Em **Links**, cola os URLs de pesquisa que geraste no separador **Onde pesquisar**.
- **Observações de preço**: regista o que vês no eBay/Cardmarket (data, fonte, preço). Para cartas é opcional (o job trata disso). **Para produto selado continua a ser a única via no plano gratuito** — ver 4e.

### Enviar os itens novos para a recolha automática
A recolha lê o ficheiro `itens.json` do repositório. Sempre que adicionares ou alterares itens na app:
1. **Exportar itens.json** (descarrega o ficheiro).
2. No GitHub (site ou app móvel): abre `itens.json` → ícone de lápis → substitui o conteúdo → **Commit changes**.
   Alternativa: **Add file → Upload files** e arrasta o ficheiro.
3. No dia seguinte (ou com **Run workflow**) os preços chegam à app.

Itens apagados na app e exportados desaparecem também do histórico automático.

### Registar compras
Separador **Portefólio → Registar compra**: item, data, quantidade, preço unitário, estado. A app compara com o último preço conhecido e mostra a variação. As compras também vão no `itens.json` exportado, para ficarem guardadas no GitHub.

### Pesquisar antes de comprar
Separador **Onde pesquisar**: escreve o nome do produto e gera links diretos para eBay vendidos (EUA e Alemanha), Cardmarket, PriceCharting, TCGplayer, população PSA, Pokellector, PokéBeach (lançamentos) e EV de selado.

## 4b. Google Sheets como base de dados (opcional, recomendado)
Substitui o `itens.json`/`dados.json`: itens, observações e compras ficam numa folha e sincronizam entre PC e telemóvel.

1. Cria uma folha com três separadores e cabeçalhos na linha 1:
   - `Folha1` (ou `Itens`): `id nome tipo set ano lang img producao ultima_reimpressao tipo_set pop_psa10 esc_override proc links notas termo_pesquisa poketrace_id ppt_tcgplayer_id criado atualizado`
   - `Observacoes`: `id item_id data fonte tier preco moeda mercado vendas avg30d origem`
   - `Compras`: `id item_id data qtd preco estado local notas`
2. Extensões → Apps Script → cola `sheets/Code.gs` → mete o `SHEET_ID` (parte do URL entre `/d/` e `/edit`) e, se quiseres, um `TOKEN`.
3. Implementar → Nova implementação → Web app → Executar como **Eu**, acesso **Qualquer pessoa** → copia o URL `…/exec`.
4. Na app: Fontes → cartão Google Sheets → cola o URL (e token) → **Ligar e sincronizar**.
5. No GitHub: Secrets `SHEETS_URL` (e `SHEETS_TOKEN`). O job diário passa a ler os itens da folha e a gravar os preços recolhidos em `Observacoes`.

Sem `SHEETS_URL`, tudo continua a funcionar com `itens.json` como antes.

## 4c. Descoberta automática de candidatos
O job diário consulta o catálogo pokemontcg.io (gratuito) e cria candidatos para todos os sets lançados nos últimos 24 meses: booster box, Elite Trainer Box e as 5 cartas mais caras (com imagem e preço Cardmarket). Aparecem no Painel em **Novos candidatos**, separados das tuas escolhas.
- **Seguir** passa o candidato para a tua lista (origem = manual); **✕** ignora-o e não volta a aparecer nesse dispositivo (e apaga-o da folha, se ligada).
- Na folha, a coluna `origem` distingue `descoberta` de `manual`.
- Ajustes em Settings → Variables: `DESCOBERTA=0` desliga; `DESCOBERTA_MESES` muda a janela. Secret opcional `POKEMONTCG_KEY` (dev.pokemontcg.io) se o limite diário de pedidos for atingido.
- Candidatos recém-lançados aparecem como **Prematuro**, sem veredito de compra: é esperado e correto. O valor está em acumular histórico desde o lançamento para que a tendência e o fim de produção os façam subir.

## 4e. Produto selado: sem fonte gratuita
Booster boxes e ETBs não têm preço automático em nenhum plano free:
- o catálogo pokemontcg.io só cobre cartas;
- o PokemonPriceTracker exige `PPT_PLAN=api` para selado;
- o TCGCSV (`backend/connectors/tcgcsv.py`) foi escrito para preencher esta lacuna, mas em 2026-09-06 passou a responder **401 Unauthorized** a pedidos anónimos. Fica **desligado por omissão**; `TCGCSV=1` volta a ligá-lo se tiveres acesso autenticado. Confirma com `cd backend && python -m connectors.tcgcsv "Evolving Skies"`.

Enquanto assim for, os selados aparecem como **Sem dados** — o que é correto: é melhor a app dizer que não sabe do que inventar uma pontuação. Para os acompanhares, regista observações manuais de preço, que entram no histórico e nas previsões como qualquer outra fonte.

## 4d. Verificar se a app estava certa (separador **Acerto**)
A pontuação de nada serve se ninguém a confrontar com o que aconteceu a seguir. Por isso:

- Em cada recolha, o job grava uma linha **imutável** na tabela `previsoes`: item, data, pontuação, veredito e preço de referência. Nunca se atualiza nem se apaga — é o registo do que a app disse, no dia em que o disse.
- Passados 90 / 180 / 365 dias, o `backend/avaliacao.py` cruza cada previsão com o preço dessa altura (±30 dias) e calcula o retorno real.
- O separador **Acerto** mostra o resultado por horizonte.

A métrica que interessa é a **Vantagem**: retorno médio dos itens marcados *Comprar* menos o retorno médio de **todos** os itens seguidos. Taxa de acerto isolada engana — num mercado a subir, "Comprar" acerta sempre. Se a Vantagem não for positiva, a pontuação não está a acrescentar informação e é a fórmula que precisa de mudar.

Duas salvaguardas contra o auto-engano:
- **Amostragem mensal**: conta-se no máximo uma previsão por item por mês. Avaliar as 365 previsões diárias do mesmo item não dá 365 observações independentes — dá uma, repetida.
- **Baseline explícito**: o universo aparece sempre na tabela, ao lado dos vereditos.

Os primeiros números só aparecem ~3 meses depois da primeira recolha. Até lá o separador diz quantas previsões estão a maturar e quanto falta.

## 5. Como é calculada a pontuação (0–100)
Um item pode não ter pontuação nenhuma, e isso é uma resposta legítima:

| Estado | Quando | O que aparece |
|---|---|---|
| **Sem dados** | nunca se recolheu um preço | sem pontuação — não é "mau", é desconhecido |
| **Prematuro** | há preço, mas menos de 21 dias de histórico | pontuação a cinzento-azul, sem veredito de compra |
| Comprar / Acompanhar / Evitar | há tendência credível | ≥ 70 / 50–69 / < 50 |

| Fator | Pontos | Origem |
|---|---|---|
| Tendência de preço | 0–30 | retorno dos **últimos 90 dias** (janela móvel), ou média 30 dias do fornecedor |
| Escassez | 0–30 | calculada (ver tabela abaixo); sobreposição manual 1–5 opcional |
| Procura | 4–20 | o valor 1–5 que defines |
| Idade do set | 0–10 | ano de lançamento |
| Tipo | 5–10 | selado pontua mais do que carta solta |

### Escassez (0–30) — porque a tiragem nunca é publicada
| Sub-fator | Pontos | Onde obter |
|---|---|---|
| Estado de produção | em produção 0 / fim anunciado 5 / fora de produção 10 | PokéBeach, anúncios oficiais |
| Meses sem reimpressão | 2 por semestre, máx. 8 (usa o ano de lançamento se não souberes) | data que registas |
| Tipo de set | principal 0 / especial 3 / promo-exclusivo 5 | catálogo |
| População PSA 10 | >5000: 0 · >2000: 1 · desconhecida: 2 · >1000: 3 · >500: 4 · ≤500: 5 | psacard.com/pop (manual) |
| Rácio vendas/anúncios | 0–2 (automático quando a API dá ambos; 1 se desconhecido) | PokeTrace / PPT |

Sobreposição manual: se souberes algo que os dados não mostram (ex.: tiragem regional confirmada), define 1–5 no item e o cálculo é ignorado.

A fórmula está em `backend/scoring.py` e é a mesma na app. É uma heurística explicável, não uma previsão — valida sempre com vendas reais antes de comprar, e usa o separador **Acerto** para saber se ela tem tido razão.

A tendência usa uma **janela móvel de 90 dias**, não o primeiro preço alguma vez observado: um item que duplicou há dois anos e está parado desde então não deve continuar a pontuar como se estivesse a subir. Preços em moedas diferentes nunca são comparados entre si — quando as fontes trocam de moeda, usa-se a que tem o histórico mais longo.

## 6. Passar a plano pago (quando quiseres)
Sem tocar no código. **Settings → Secrets and variables → Actions → Variables → New repository variable**:
- `POKETRACE_PLAN` = `pro` → liga Cardmarket/EUR, graduadas PSA/BGS/CGC, histórico do fornecedor.
- `PPT_PLAN` = `api` → liga produtos selados e cartas japonesas; `business` liga Cardmarket EUR.

Depois sobe o `DAILY_BUDGET_*` em `backend/.env.example` se precisares de mais pedidos (o job protege-se para não ultrapassar o limite diário).

## 7. Correr localmente (opcional)
```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # preenche as chaves
python job.py                   # gera ../dados.json
```
Para a app ler o `dados.json` local, serve a raiz com `python -m http.server 8080` e abre `http://localhost:8080`.

## 8. Resolução de problemas
| Sintoma | Causa provável | Solução |
|---|---|---|
| "Ainda não há recolha" | Workflow nunca correu | Actions → Run workflow |
| Workflow falha em "git push" | Permissões | Passo 1.5 |
| Item sem preço automático | Nome não encontrado na API | Ajusta o nome (inclui número e set) ou regista observações manuais |
| Selado marcado "Sem dados" | Não há fonte gratuita para selado | Esperado — ver 4e. Regista observações manuais na app |
| Separador Acerto vazio | Ainda não passaram 60+ dias desde a primeira recolha | Normal — o ecrã diz quanto falta |
| Preços em USD | Plano free só tem mercado US | `POKETRACE_PLAN=pro` para EUR |
| App não guarda no telemóvel | Modo privado/incógnito | Abre em janela normal e adiciona ao ecrã principal |

## Estrutura
```
index.html           app (HTML + CSS + JS), PWA, PT/EN, câmara + OCR
itens.json           os teus itens e compras (fonte de verdade para a recolha)
dados.json           gerado pelo job: preços, pontuação, veredito
manifest.json, sw.js, icon.svg   instalação como app no telemóvel
backend/job.py       recolha + exportação
backend/scoring.py   fórmula da pontuação
backend/avaliacao.py cruza previsões passadas com os preços que vieram a seguir
backend/connectors/  um ficheiro por fornecedor de dados (inclui tcgcsv.py, selado gratuito)
backend/pokevalor.db histórico próprio: snapshots (preços) + previsoes (o que a app disse)
.github/workflows/diario.yml   agendamento diário
```
