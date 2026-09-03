# CC-continue — návrh

Datum: 2026-09-03

## Cíl

Osobní TUI nástroj (inspirovaný vzhledem RalphTui), přes který lze:

- zadávat prompty do fronty pro konkrétní projekt,
- nechat je automaticky odbavovat Claude Code na pozadí — i když aktuální
  běh doběhne (task hotový) nebo narazí na usage limit a čeká na reset,
- vidět historii toho, kdy jaký prompt běžel a s jakým výsledkem,
- sledovat základní analytiku (náklady, tokeny, čas strávený čekáním na
  reset limitu).

Řeší problém: uživatel běžně pouští víc souběžných Claude Code session
v tmuxu pro různé projekty a chce je nechat pracovat i mimo PC, bez
ručního psaní "pokračuj" po resetu limitu a bez ručního hlídání front.

## Ověřené technické předpoklady

Ověřeno v izolované tmux session testem proti reálnému `claude` CLI
(verze 2.1.259):

- `claude --session-id <uuid> -p "<prompt>" --output-format json
  --dangerously-skip-permissions` spustí headless běh s pevným ID session.
- `claude --resume <uuid> -p "<prompt>" --output-format json
  --dangerously-skip-permissions` navazuje na kontext stejné session
  (ověřeno: model si pamatoval předchozí odpověď).
- Úspěšný běh vrací na stdout jeden JSON objekt s poli mj. `session_id`,
  `is_error`, `total_cost_usd`, `usage.{input,output,cache_*}_tokens`,
  `duration_ms`, `num_turns`, `result`, `subtype` — dost pro historii i
  analytiku.
- Neplatné/neexistující session ID selže rychle a levně: prázdný stdout,
  exit code 1, čitelná chyba na stderr (`No conversation found with
  session ID: ...`) — bez API volání, takže detekce je zadarmo.
- Přesný textový tvar hlášky o usage limitu nebyl v testu ověřen (nechtěl
  jsem záměrně vyčerpat limit) — detekce rate limitu proto musí mít i
  fallback, ne spoléhat jen na jeden regex (viz níže).

## Architektura

```
Textual TUI  →  asyncio orchestrátor (1 task/fronta, fronty běží souběžně)
             →  prompt runner (subprocess `claude -p --resume`)
             →  SQLite (historie, stav front, analytika)
```

- **Jedna fronta = jeden projekt** (adresář + pevné session ID). Fronty
  běží souběžně mezi sebou, uvnitř fronty se prompty odbavují sekvenčně.
- Orchestrátor a TUI běží ve stejném procesu (MVP). Aby automatizace
  fungovala přes noc, musí `cc-continue` proces zůstat spuštěný — typicky
  v jedné dlouhotrvající tmux/screen session (stejná potřeba jako dřív,
  jen sjednocená do jednoho procesu místo hlídání víc oken ručně).
- Všechny běhy jedou s `--dangerously-skip-permissions` (podle tvého
  rozhodnutí — plná automatizace, žádné čekání na schválení nástrojů).

## Datový model (SQLite, `~/.local/share/cc-continue/history.db`)

- **queues**: `id, name, project_path, session_id, status
  (idle|running|waiting_retry|blocked_error), next_retry_at, last_error,
  created_at, updated_at`
- **queue_items**: `id, queue_id, prompt_text, position, status
  (pending|running|done|failed|skipped), added_at`
- **prompt_runs**: `id, queue_id, queue_item_id, prompt_text, started_at,
  finished_at, status (success|rate_limited|error), cost_usd,
  input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
  duration_ms, num_turns, result_text, error_text`

SQLite je zdroj pravdy pro stav front — TUI je jen náhled/ovladač.
Restart appky neztratí čekající prompty.

## Chování fronty (trigger logika)

Pro každou frontu smyčka: je-li stav `idle` a existuje čekající položka →
spustit runner → podle výsledku:

1. **success** (`is_error:false`) → zapsat run, položku označit `done`,
   frontu zpět na `idle` → **okamžitě zkusit další čekající prompt**
   (auto-advance). Prázdná fronta → `idle`, čeká na nový prompt přidaný
   z TUI.
2. **rate_limited** (detekce: shoda na fráze typu „usage limit", „limit
   reached", „resets at" ve stdout/stderr, nebo `is_error:true` s
   takovým obsahem) → prompt **zůstává ve frontě** (zkusí se znovu, ne
   promarněný), stav fronty `waiting_retry`. Pokud jde z hlášky vyparsovat
   čas resetu → naplánovat retry přesně na něj; jinak fallback backoff
   15 → 30 → 60 min (strop 60 min, reset zpět na 15 min po dalším
   úspěchu). Ostatní fronty běží dál bez ovlivnění.
3. **hard error** (jiná chyba — špatný prompt, nástroj selhal, crash) →
   zapsat run jako `error`, položku `failed`, **frontu zastavit**
   (`blocked_error`) a čekat na ruční zásah v TUI (retry/skip). Důvod:
   nechceme tiše dokola pálit kredit na rozbitou frontu.

Při startu appky: běhy, co zůstaly v `prompt_runs` se stavem odpovídajícím
neukončenému běhu z předchozího pádu, se označí jako přerušené a jejich
položka se vrátí na `pending` — automaticky se zkusí znovu.

Doplňující pravidla k nejednoznačným případům:

- Čas resetu parsovaný z hlášky se interpretuje v místním časovém pásmu
  systému, pokud hláška sama neuvádí jinou zónu explicitně.
- Pokud `--resume <session_id>` selže s „No conversation found" (session
  na straně Claude Code zanikla/byla promazána), klasifikuje se to jako
  **hard error**, ne jako důvod tiše založit novou session — frontu to
  zastaví a v TUI půjde ručně zvolit „založit novou session pro tuto
  frontu" (vygeneruje nové `session_id`, historie předchozích běhů
  zůstává zachovaná).

## TUI (Textual)

1. **Dashboard** — tabulka front: projekt, stav (`● idle / ▶ running /
   ⏳ čeká do HH:MM / ✖ chyba`), počet čekajících promptů, dnešní
   náklady. Klávesy: `n` nová fronta, `a` přidat prompt, `Enter` detail,
   `r` retry zablokované fronty, `q` konec.
2. **Detail fronty** — seznam čekajících promptů (přidat/smazat/přeřadit),
   běžící prompt (spinner + uplynulý čas — plný streaming výstupu nechávám
   jako pozdější vylepšení, ne v MVP), historie běhů dané fronty.
3. **Analytika** — náklady/tokeny za den (posledních 30 dní), náklady
   podle projektu, počet promptů za den, celkový čas strávený čekáním na
   reset limitu, počty success/error/rate_limited.

## CLI

- `cc-continue` — spustí TUI.
- `cc-continue add <cesta-k-projektu> "<prompt>"` — přidá prompt do fronty
  bez otevření TUI (založí frontu, pokud pro danou cestu ještě neexistuje).
  Užitečné pro rychlé zadání z jiného terminálu nebo skriptu.

## Testování

- Unit testy (pytest): klasifikátor výstupu runneru (success/rate_limited/
  error) na fixture datech, parser reset-času, výpočet backoffu, storage
  vrstva.
- Protože reálný rate limit nejde bezpečně vyvolat na požádání (stálo by
  to skutečný limit), runner půjde přepnout do mock režimu (env proměnná),
  který vrací nafingovaný `rate_limited`/`error` výsledek bez volání
  `claude` — umožní to otestovat retry/backoff/analytiku deterministicky.
- Ruční smoke test: `cc-continue add . "levný testovací prompt"`, spustit
  TUI, ověřit že běh proběhne, objeví se v historii a v analytice —
  se stejně levnými prompty jako při dnešním ověřování.

## Vědomé zjednodušení pro MVP (YAGNI)

- Žádné per-frontu nastavení oprávnění — vždy plný `--dangerously-skip-
  permissions`, jak sis vybral.
- Žádný live streaming výstupu běžícího promptu v MVP, jen spinner +
  finální výsledek po doběhnutí.
- Orchestrátor běží v procesu TUI (ne jako oddělený daemon/systemd
  service) — jednodušší, ale appka musí zůstat spuštěná (v tmuxu), aby
  fronty pokračovaly přes noc.
