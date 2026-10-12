# Automatické pokračování po limitu a fronta úkolů — návrh

Datum: 2026-10-12

## Cíl

cc-continue nahrazuje běžné používání Claude Code v CLI. Pro jeho
konverzace (ne pro interaktivní sessions v jiných terminálech) chceme:

1. u každé konverzace nastavit, jestli má po vyčerpání limitu sama
   pokračovat,
2. reset limitu poznat ze skutečného sledování využití (usage API), ne
   z hádání podle textu hlášky,
3. pohodlně plnit frontu úkolů, aby Claude po dokončení jedné práce
   pokračoval další.

## 1. Přepínač auto-continue

- `queues.auto_continue INTEGER NOT NULL DEFAULT 1`. Existující fronty
  dostanou 1 → jejich chování se nemění.
- Okno New conversation: zaškrtávátko *Auto-continue after usage limit*
  (výchozí zaškrtnuté), mimo skupiny přepínačů `claude`.
- Přepíná se v editoru fronty (klávesa `o`, viz bod 4). Hlavička
  konverzace ukazuje `auto-continue on` / `auto-continue off`.

## 2. Chování při limitu

- **auto_continue = 1:** stav `waiting_retry` s `next_retry_at`; po resetu
  démon sám pokračuje.
- **auto_continue = 0:** nový stav `paused_limit` (`QueueStatus.PAUSED_LIMIT`)
  s `next_retry_at` = očekávaný reset. Nic se samo nespustí. Stavový řádek:
  před resetem „Paused at usage limit, resets HH:MM“, po něm „Limit reset —
  press r to continue“. Pokračuje se klávesou `r` nebo odesláním nové
  zprávy (obojí přepne stav na `idle`).
- **Co se pošle po resetu:** při limitu démon zkontroluje přepis session —
  je-li poslední lidská zpráva v přepisu shodná s textem, který právě
  poslal, rozběhnutá zpráva se do konverzace dostala → položka dostane
  `continue_on_retry = 1` a při dalším pokusu se místo ní pošle *continue
  text*. Jinak (limit hned na začátku, přepis neexistuje) se pošle znovu
  původní text.
- *Continue text* je v nové tabulce `settings` pod klíčem `continue_text`,
  výchozí „Pokračuj tam, kde jsi skončil.“. Nastavení:
  `cc-continue config continue-text "…"`, bez hodnoty vypíše aktuální.
- V historii běhů (`prompt_runs.prompt_text`) je text skutečně odeslaný.
- Živé (live-terminal) fronty se nemění.

## 3. Detekce resetu přes sledování využití

Nový čistý modul `cc_continue/limits.py` (bez I/O):

- `exhausted_until(usage, now) -> datetime | None` — je-li některé okno
  (5h, týdenní, per-model) na ≥ 100 %, vrátí nejpozdější `resets_at` mezi
  vyčerpanými okny + 30 s rezervy; jinak `None`.
- `retry_time_after_rate_limit(usage, now) -> datetime | None` — po 429:
  okno s nejvyšším využitím → jeho `resets_at` + 30 s, je-li v budoucnu;
  `None`, když využití není k dispozici.
- Časy se vrací jako naivní lokální čas (jako zbytek `queues.next_retry_at`).

Démon (orchestrátor):

- Využití čte přes `usage_api.get_pro_usage` (sdílená 60s cache s TUI),
  v samostatném vlákně (`asyncio.to_thread`).
- **Po 429:** `get_pro_usage(force_refresh=True)` →
  `retry_time_after_rate_limit`; když `None`, dnešní záloha (`parse_reset_time`
  z hlášky, jinak 15→30→60 min).
- **Preventivně:** má-li fronta čekající položku, před jejím spuštěním
  `exhausted_until(get_pro_usage())`; je-li čas, Claude se nespouští a fronta
  přejde do `waiting_retry`/`paused_limit` s tímto časem.
- **Čekání:** smyčka fronty respektuje `waiting_retry` + `next_retry_at`
  (spí po kouscích max. `POLL_INTERVAL_SECONDS`, aby zachytila změny z TUI).
  Po uplynutí času se využití načte bez cache; je-li okno pořád vyčerpané,
  čeká se znovu. Díky perzistenci stavu čekání přežije i restart démona.
- Využití se tedy dotazuje jen při spouštění položky a při čekání na
  limit — ne pořád dokola.

## 4. Editor fronty úkolů

V Conversations klávesa `t` otevře okno **Tasks** aktuální konverzace:

- nahoře stav: `Auto-continue: on/off (o)` · `Queue: running/paused (p)`,
- tabulka čekajících úkolů v pořadí (číslo, první řádek textu),
- `a` přidat (víceřádkový editor, `Ctrl+S` uloží, `Esc` zruší),
  `e` / `Enter` upravit, `Delete` smazat (položka → `skipped`, v historii
  zůstane), `Ctrl+↑` / `Ctrl+↓` přesunout, `p` pozastavit/spustit frontu,
  `o` přepnout auto-continue, `Esc` zavřít.
- `queues.paused INTEGER NOT NULL DEFAULT 0`: pozastavená fronta nespouští
  další položky (rozběhnutá doběhne). Stavový řádek: „Queue paused — t, p to
  resume“.
- Úkoly běží postupně ve stejné session (Claude zná kontext předchozích);
  další začne, jakmile předchozí běh skončí úspěšně. Pole pro zprávu pod
  přepisem přidává na konec téže fronty.
- Upravovat/mazat/přesouvat jde jen čekající (`pending`) položky.

## Data (migrace stejným vzorem jako dřív)

- `queues.auto_continue INTEGER NOT NULL DEFAULT 1`,
  `queues.paused INTEGER NOT NULL DEFAULT 0`
- `queue_items.continue_on_retry INTEGER NOT NULL DEFAULT 0`
- `CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)`
- Modely: `Queue.auto_continue: bool = True`, `Queue.paused: bool = False`,
  `QueueItem.continue_on_retry: bool = False`, `QueueStatus.PAUSED_LIMIT`.
- Storage: `set_queue_auto_continue`, `set_queue_paused`,
  `set_item_continue_on_retry`, `update_item_text`, `skip_item`,
  `move_item(item_id, delta)`, `get_setting`, `set_setting`;
  `create_queue(..., auto_continue=True)`.

## Testy

- `limits`: žádné / jedno / více vyčerpaných oken, per-model okno, reset
  v minulosti, nedostupné využití.
- Orchestrátor (využití podstrčené, žádná síť v testech — autouse fixture):
  auto on → `waiting_retry` a po čase pokračuje; auto off → `paused_limit`
  a nic se nespustí; continue text vs. původní; preventivní čekání bez
  spuštění Claude; pozastavená fronta; restart démona během čekání.
- Storage: migrace, přesuny, úpravy, skip, settings.
- CLI `config continue-text`.
- TUI: editor fronty (přidat, upravit, smazat, přesunout, `p`, `o`),
  stavové řádky `paused_limit` a paused, `r` z `paused_limit`, checkbox
  v okně New conversation.
