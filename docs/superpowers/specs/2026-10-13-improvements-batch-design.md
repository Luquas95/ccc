# Sada vylepšení ccc — návrh

Datum: 2026-10-13. Funkce se implementují postupně v tomto pořadí, každá
ve vlastní větvi; po zelených testech se rovnou slučuje do `main` a
restartují se služby (rozhodnutí uživatele).

## 4. Heartbeat démona

- Démon každých `HEARTBEAT_SECONDS = 10` zapíše do `settings`
  `daemon_heartbeat` = ISO čas (samostatná asyncio úloha v `daemon._run`).
- TUI (všechny obrazovky, `SidebarScreen`): pod titulkem v sidebaru řádek
  `● daemon running` (zeleně) / `✖ daemon not running` (červeně, když
  heartbeat chybí nebo je starší než 30 s). Obnovuje se každé 2 s.

## 9. Víceřádkové pole pro zprávu

- Pole pod přepisem je `TextArea` (výška 3, roste do 8 řádků).
  `Enter` odešle, `Shift+Enter` / `Ctrl+J` vloží nový řádek (Shift+Enter
  jen tam, kde ho terminál rozliší — Ctrl+J funguje vždy). Id zůstává
  `#message-input`.

## 8. Předvolby v okně New conversation

- Poslední použitý výběr (atributy + auto-continue + remote control) se
  uloží do `settings` `last_launch_selection` (JSON) a okno se jím
  předvyplní (session skupina se vždy vrací na *New session*).
- Pojmenované předvolby: `settings` `launch_presets` (JSON
  `{name: {selection, auto_continue, remote_control}}`). V okně nahoře
  `Select` „Preset“ (výběr přepíše zaškrtnutí) a tlačítko *Save as preset*
  (zeptá se na název; existující název přepíše).

## 6. Markdown odpovědí a výstupy nástrojů

- Odpověď Clauda se vykreslí widgetem `Markdown` (nadpisy, seznamy,
  kód) uvnitř zeleného rámečku; lidské zprávy zůstávají prostý text.
- Volání nástroje je řádek `⚙ Název: náhled`; Enter / klik ho rozbalí na
  celý vstup nástroje a jeho výsledek (`tool_result` z přepisu, oříznuté
  na 4000 znaků). Transcript parser proto nově vrací i `tool_result`
  události spárované s voláním přes `tool_use_id`.

## 7. Hledání a export

- `/` v Conversations otevře okno hledání: textové pole, výsledky napříč
  všemi (i archivovanými) konverzacemi — název konverzace, čas, úryvek
  s nálezem. Enter otevře konverzaci (bez posunu na nalezenou zprávu —
  zobrazuje se jen posledních 60 zpráv, starší nález by nebyl na obrazovce).
  Hledá se v přepisech (case-insensitive podřetězec), max. 200 výsledků.
- `e` v Conversations exportuje vybranou konverzaci do
  `~/Documents/ccc-exports/<název>-<datum>.md` (zprávy, nástroje jako
  odrážky) a cestu ukáže v notifikaci.

## 1. Telegram

- Konfigurace: `ccc config telegram-token <TOKEN>`,
  `ccc config telegram-chat <CHAT_ID>`, `ccc config telegram-test`
  (pošle zkušební zprávu). Bez tokenu/chatu se nic neposílá.
- Události (všechny zapnuté):
  - **fronta hotová** — poslední úkol konverzace doběhl úspěšně a fronta
    je prázdná (+ prvních 300 znaků odpovědi),
  - **potřebuje tě** — `paused_limit`, nebo čekající žádost o schválení
    nástroje (bod 2),
  - **chyba** — fronta přešla do `blocked_error` (+ chyba),
  - **limit / reset** — přechod do `waiting_retry` („čeká do HH:MM“) a
    návrat z něj („pokračuje“).
- Odesílá démon (HTTPS Bot API `sendMessage`, stdlib `urllib`), v
  samostatném vlákně, chyby jen zaloguje. Token se nikdy neloguje.
- Notifikace vyvolává orchestrátor na přechodech stavů (centrálně v
  `Storage.update_queue_status` se nehlídá — hook je v `QueueRuntime`).

## 5. Diff a auto-commit po úkolu

- Jen pro headless konverzace v git repozitáři.
- Před spuštěním úkolu: `git rev-parse HEAD` + `git status --porcelain`
  uloží se do `prompt_runs.git_before` (HEAD) — kvůli rozlišení změn.
- Po úspěšném úkolu: pokud jsou změny (`git status --porcelain`
  neprázdný), `git add -A` + `git commit -m "ccc: <první řádek úkolu>"`
  (+ řádek `ccc-conversation: <název>`); hash do `prompt_runs.git_commit`.
  Neprovede se, když HEAD mezitím není na větvi (detached) nebo commit
  selže (zaloguje a pokračuje, úkol zůstává úspěšný).
- TUI: v detailu fronty u běhu sloupec *Commit*; `Enter` na běhu otevře
  okno se `git show --stat` + diff (oříznuto, scrollovatelné).

## 10. Plánování úkolů

- `queue_items.not_before TEXT NULL`. Úkol s budoucím `not_before` se
  přeskakuje (fronta bere první úkol, jehož čas nastal); ostatní úkoly
  za ním čekají (pořadí se zachovává — plánovaný úkol blokuje frontu).
- Editor úkolu (Tasks → a/e): pole *Run at* (`HH:MM`, `YYYY-MM-DD HH:MM`,
  nebo `reset` = až po příštím resetu 5h okna podle usage). Tabulka úkolů
  ukazuje sloupec *When*.

## 2. Schvalování nástrojů z TUI

- Týká se headless konverzací bez „Skip all permission checks“. S ním
  (yolo) se nic nemění — vše se schvaluje automaticky.
- Mechanismus Claude Code: `--permission-prompt-tool mcp__ccc__approve`
  + `--mcp-config` s MCP serverem `ccc-permission-mcp` (stdio, součást
  balíčku). Nástroj zapíše žádost do tabulky `permission_requests`
  (queue, tool, input JSON, čas, stav) a **čeká bez omezení** na
  rozhodnutí; vrací `{"behavior":"allow","updatedInput":…}` nebo
  `{"behavior":"deny","message":"Denied by user in ccc"}`.
- TUI: konverzace s čekající žádostí má ikonu `?` (žlutě), stavový řádek
  „Waiting for your approval — p“; klávesa `p` v Conversations otevře
  okno s nástrojem a vstupem: `y` povolit, `a` povolit vždy pro tento
  nástroj v této konverzaci, `n` zamítnout. Telegram „potřebuje tě“.
- Remote-control konverzace mají dotazy přímo v interaktivní session
  (schvaluje se z mobilu / claude.ai) — beze změny.
