# Nová konverzace z TUI (spouštění Claude Code) — návrh

Datum: 2026-10-12

## Cíl

cc-continue má umět samo spustit Claude Code: uživatel v TUI založí novou
konverzaci, zvolí adresář, zaškrtne atributy (přepínače `claude`) a pak s
konverzací píše přímo v pohledu Conversations. Účel programu je být
rozhraním pro tyto konverzace — ne odkazovat do jiného terminálu.

## Rozhodnutí

- **Mechanismus: headless přes démona.** Nová konverzace = nová fronta
  (vlastní UUID session, adresář, atributy). Každou zprávu z TUI démon
  pustí jako `claude -p ... --output-format json <atributy>`. Fronta,
  pokračování po limitu i analytika tak fungují beze změny a konverzace
  běží i se zavřeným TUI. Daň: nejde schvalovat nástroje za běhu ani
  používat interaktivní slash příkazy — oprávnění se volí předem atributem.
- **Pevný seznam atributů** (v kódu, ne konfigurák).
- **Výběr adresáře:** naposledy použité + strom adresářů + ruční cesta.
- Jazyk UI zůstává anglický jako zbytek TUI.

## Ověřené předpoklady (claude 2.1.296, naživo)

- `claude -p --resume <id> --fork-session` vrátí v JSON výstupu **nové**
  `session_id` (původní session zůstane netknutá).
- Přepisy jsou v `~/.claude/projects/<kódovaný-adresář>/<session_id>.jsonl`,
  kódování = každý znak kromě písmen a číslic → `-`. `~/DEV` je symlink na
  `/mnt/AI/DEV`, takže se pro adresář musí zkusit kódování zadané cesty
  i její `realpath`.
- Přepis se během `-p` běhu průběžně zapisuje, takže 2s obnovování
  v Conversations ukazuje postup i během dlouhého běhu.

## Atributy

Skupiny označené *(jedna)* jsou výlučné: zaškrtnutí položky odškrtne
ostatní ve skupině. Lze odškrtnout vše (= výchozí chování `claude`),
kromě Oprávnění a Session, které mají vždy právě jednu volbu.

| Skupina | Položka | Přepínače |
|---|---|---|
| Session *(jedna, výchozí New)* | New session | `--session-id <nové uuid>` |
| | Continue last in directory | převede se při startu na `--resume <id nejnovější session v adresáři>` |
| | Resume selected… | `--resume <vybrané id>` (seznam sessions adresáře: datum, první zpráva, počet zpráv) |
| | From pull request… | `--from-pr <číslo/URL>` |
| Session — nezávislé | As a copy (fork) | `--fork-session`; aktivní jen u Continue/Resume/From PR |
| Permissions *(jedna, výchozí první)* | Skip all permission checks | `--dangerously-skip-permissions` |
| | Auto-accept edits | `--permission-mode acceptEdits` |
| | Plan only | `--permission-mode plan` |
| Model *(jedna)* | Opus / Sonnet / Haiku / Fable | `--model opus` / `sonnet` / `haiku` / `fable` |
| Effort *(jedna)* | high / xhigh / max | `--effort high` / `xhigh` / `max` |
| Other | Fallback to Sonnet when overloaded | `--fallback-model sonnet` |
| | Claude in Chrome | `--chrome` |
| | Safe mode (no customizations) | `--safe-mode` |

Úmyslně vynecháno: `--worktree` (každé `-p` by zakládalo nový worktree),
`--bare` (nefunguje s OAuth), `--restricted` (koliduje s bypass
oprávněním), `--remote-control` (jen interaktivně), `--teleport`/`--cloud`
(cloudové sessions), `--desktop` (otevírá aplikaci).

## Data

Tabulka `queues` dostane dva sloupce (migrace stejným vzorem jako
`always_resume`):

- `launch_flags TEXT NULL` — JSON seznam trvalých přepínačů posílaných při
  **každém** běhu (oprávnění, model, effort, ostatní). `NULL` = fronta
  z doby před touto funkcí → runner použije dosavadní
  `--dangerously-skip-permissions`, nic se nemění.
- `first_run_flags TEXT NULL` — JSON seznam jednorázových přepínačů jen pro
  **první úspěšný** běh: `["--fork-session"]` nebo `["--from-pr", "<x>"]`.
  Po prvním úspěšném běhu démon uloží `session_id` vrácené Claude Code do
  fronty a `first_run_flags` vymaže, další zprávy už jdou do té session.

Session při založení:

- New → nové UUID, `always_resume = 0` (první běh `--session-id`).
- Continue last / Resume selected → `session_id` = nalezené/vybrané id,
  `always_resume = 1`. **Pokud pro to id už fronta existuje a není to
  fork, nová fronta nevznikne** — TUI jen přepne na existující konverzaci.
- Fork (s Continue/Resume) → protože `session_id` je UNIQUE a fronta pro
  původní session může existovat, uloží se do fronty zástupné UUID a
  `first_run_flags = ["--resume", "<původní id>", "--fork-session"]`.
  Po prvním úspěšném běhu se zástupné UUID nahradí id kopie.
- From PR → zástupné UUID, `first_run_flags = ["--from-pr", "<x>"]`
  (+ `--fork-session`, je-li zaškrtnuto).

Runner: pokud `first_run_flags` obsahuje `--resume` nebo `--from-pr`,
vlastní `--session-id/--resume` z fronty se nepřidává (session určují ony).
Kolize při uložení vráceného `session_id` (už patří jiné frontě) → chyba
fronty „session already has a conversation in cc-continue“.

## Komponenty

- `cc_continue/launch_options.py` — definice skupin/položek, `build_flags()`
  (výběr → trvalé + jednorázové přepínače), `describe_flags()` (přepínače →
  krátké popisky pro zobrazení). Čistý kód bez I/O.
- `cc_continue/transcript.py` — `list_sessions_for_directory(path)`:
  sessions adresáře seřazené od nejnovější (id, čas změny, první zpráva,
  počet zpráv), max. 50 nejnovějších souborů.
- `cc_continue/storage.py` — sloupce, `recent_project_paths()`,
  `list_pending_items()`, `set_queue_session()`; `create_queue()` přijme
  `launch_flags` a `first_run_flags`.
- `cc_continue/orchestrator.py` — `start_conversation(...)` (založení fronty
  podle výběru), předávání přepínačů do `run_fn`, uložení nového
  `session_id` po prvním běhu.
- `cc_continue/runner.py` — `execute(..., flags)`.
- `cc_continue/tui/new_conversation.py` — `NewConversationModal`.
- `cc_continue/tui/conversations.py` — tlačítko a klávesa New conversation,
  hlavička konverzace s atributy, stavový řádek, šedé bubliny „queued“,
  pole pro zprávu (Enter = odeslat), průběžné doplňování nových front do
  seznamu, výběr konverzace po založení.
- `cc_continue/tui/layout.py` — globální klávesa `n`.
- `cc_continue/tui/queue_detail.py` — řádek s atributy.

## UI

Okno New conversation (modální, ve stylu ostatních oken):

- Vlevo: **Recent directories** (z existujících front, od nejnovější),
  **strom adresářů** od `~/DEV`, pole **Path** (výběr ve stromu/seznamu ho
  vyplní; ověří se, že adresář existuje).
- Vpravo: skupiny atributů jako zaškrtávátka. Pod *Resume selected…* se
  ukáže seznam sessions zvoleného adresáře, pod *From pull request…* pole
  pro číslo/URL. *As a copy (fork)* je zakázané, dokud není zvolena
  obnovovací volba.
- Dole: volitelný **Name** (výchozí = název adresáře), tlačítka **Start**
  (zelené) / **Cancel** (červené), Esc = zrušit.
- Chyby (neexistující adresář, žádná předchozí session pro Continue,
  nevybraná session pro Resume, prázdné PR) se ukážou v okně, nic se
  nezaloží.

Conversations:

- Sidebar tlačítka: **New conversation (n)** zelené, Live sessions modré,
  Retry blocked červené. `n` funguje z každé obrazovky (po založení se
  přepne do Conversations na novou konverzaci).
- Nad přepisem hlavička: název · adresář · atributy.
- Pod přepisem stavový řádek (Claude is working… / Waiting for usage limit
  reset until HH:MM / Blocked: <chyba> — press r / N queued) a jednořádkové
  pole pro zprávu. Víceřádkové prompty dál přes Add prompt (`a`).
- Zprávy ve frontě (ještě neodeslané Claude Code) se zobrazí na konci
  přepisu jako šedé bubliny s označením *queued*.

## Testy

- `launch_options`: výchozí výběr, výlučné skupiny, každá session volba →
  správné trvalé/jednorázové přepínače, `describe_flags`.
- Storage: migrace staré DB, nové metody.
- Runner: sestavení příkazu (legacy bez flags, s flags, s `--from-pr`,
  s `--resume ... --fork-session`) — přes mock `create_subprocess_exec`.
- Orchestrátor: první běh s `first_run_flags` uloží nové `session_id`
  a vymaže je; chyba/limit je ponechá; legacy fronty beze změny.
- `list_sessions_for_directory`: kódování cesty i realpath, řazení, první
  zpráva.
- TUI: okno (výběr adresáře ze seznamu/stromu/ručně, chyby, Start založí
  frontu, existující session → přepnutí), Conversations (pole pro zprávu
  zařadí prompt, queued bubliny, stavový řádek, nová fronta se objeví
  v seznamu).
- Ruční ověření naživo: nová konverzace s Haiku v testovacím adresáři,
  jedna zpráva, odpověď v Conversations.
