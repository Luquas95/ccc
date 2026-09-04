# Conversation view — návrh

Datum: 2026-09-04

## Cíl

CC-continue zatím ukazuje jen poslední výsledek promptu (`prompt_runs.result_text`)
v Queue Detail — ne celý průběh konverzace. Uživatel chce v `ccc` vidět **celou
konverzaci** dané fronty jako plynoucí chat, ve stylu obrazovky, kterou ukázal
(boxy zpráv s hlavičkou odesílatele a časem, tmavé "cyber" pozadí, vlevo seznam
konverzací/vpravo obsah).

## Zjištění z průzkumu

- Claude Code ukládá **kompletní** transkript každé session (uživatelské i
  Claudovy zprávy, tool_use bloky, thinking bloky, metadata) jako JSONL soubor
  pod `~/.claude/projects/<zakódovaná-cesta>/<session_id>.jsonl`.
- Toto platí **stejně pro headless i live-terminal fronty** — obě zapisují do
  souboru se stejným `session_id`, takže stačí jeden čtecí mechanismus pro obě.
- Zakódovaná cesta nahrazuje libovolný nealfanumerický znak pomlčkou (ne jen
  `/`) — rekonstrukce cesty by byla křehká. Robustnější je dohledat soubor podle
  `session_id` (UUID, fakticky globálně unikátní) prohledáním
  `~/.claude/projects/**/<session_id>.jsonl`. Ověřeno naživo: ~7ms i mezi 385
  existujícími soubory.
- `claude logs <id>` (vestavěný příkaz) funguje jen pro krátkodobé background
  joby evidované v `claude agents`, ne pro libovolné `session_id` — není náhrada
  za vlastní čtení JSONL.
- Formát řádků: `type` pole rozlišuje `user`/`assistant`/`system`/`cost-state`/
  `bridge-session`/atd. `user` řádek s `message.content` jako **řetězec** je
  skutečná lidská zpráva; `message.content` jako **pole** bývá syntetický
  tool-result vracený zpět modelu (ne lidský vstup). `assistant` řádek má
  `message.content` jako pole bloků: `text` (odpověď), `tool_use` (použití
  nástroje), `thinking` (skryté uvažování, přeskočit).

## Rozsah (supersede)

Tenhle návrh **nahrazuje** dřívější plán "nová obrazovka dostupná z Queue
Detail" (zmíněný cestou při brainstormingu) — místo toho jde o **samostatnou
obrazovku nejvyšší úrovně**, dostupnou přímo z dashboardu, s vlastním
přepínáním mezi frontami. Queue Detail (historie běhů) zůstává beze změny,
existuje vedle ní.

## Architektura

Nový modul `src/cc_continue/transcript.py` (čistě datová vrstva, bez UI):

- `find_transcript_path(session_id: str) -> Path | None` — prohledá
  `~/.claude/projects/**/<session_id>.jsonl`.
- `TranscriptEvent` dataclass: `kind` (`"human" | "assistant_text" |
  "tool_call"`), `text: str`, `timestamp: datetime`.
- `parse_transcript_events(path: Path, since_byte_offset: int = 0) ->
  tuple[list[TranscriptEvent], int]` — inkrementální parser: přečte od
  daného bajtového offsetu, vrátí nové události + nový offset. Offset se
  posune jen za poslední **kompletní** řádek (soubor může být zapisován
  živě, poslední řádek může být rozepsaný) — nekompletní/nerozparsovatelný
  řádek se zkusí znovu příští volání.

Pravidla filtrování (viz Zjištění výše):
- lidská zpráva: `type=user` a `message.content` je `str` → `kind="human"`
- text Clauda: `type=assistant`, bloky `type=text` z `message.content` →
  `kind="assistant_text"`
- použití nástroje: bloky `type=tool_use` → `kind="tool_call"`, text ve
  tvaru `<tool_name>: <input jako json.dumps, ořezaný na 80 znaků + "…"
  je-li delší>` (žádné nástroj-specifické formátování — YAGNI pro v1, např.
  ne zvlášť pro Bash/Edit/Write)
- přeskočeno vždy: `thinking` bloky, `type=user` s `content` jako pole
  (syntetický tool-result), všechny ostatní `type` hodnoty (`system`,
  `cost-state`, `bridge-session`, `mode`, `permission-mode`, atd.)

Nová TUI obrazovka `src/cc_continue/tui/conversations.py`:
`ConversationsScreen(storage)` — rozdělení vlevo/vpravo (`Horizontal`):

- **Levý panel** (pevná šířka 32 sloupců): seznam front
  (`storage.list_queues()`), jedna položka na řádek, jen `queue.name` (bez
  statusu/pendingu — na to slouží dashboard, tady jde čistě o výběr
  konverzace). Pohyb kurzoru šipkami nahoru/dolů **okamžitě** překreslí
  pravý panel na konverzaci nově zvýrazněné fronty (bez nutnosti Enter).
- **Pravý panel**: scrollovatelný sloupec "message boxů" — jeden na
  událost transkriptu vybrané fronty. Lidská zpráva a text Clauda jsou v
  ohraničeném boxu s hlavičkou (`"You"` pro `kind="human"`, `"Claude"` pro
  `kind="assistant_text"`) a časem vpravo dole v boxu ve formátu `%H:%M`
  (lokální čas); `tool_call` je neohraničený, ztlumený jednořádkový text
  mezi boxy bez vlastního času (ne plná bublina — jinak by dlouhá session s
  hodně nástroji zahltila obrazovku).
- **Spodní panel**: zatím obyčejný Textual `Footer` (klávesové zkratky),
  bez vlastního stylu — přestylování je záměrně odloženo ("necháme zatím").
- Živá obnova: pravý panel se každé 2s (stejný rytmus jako dashboard)
  dočte o nové bajty ze souboru **jen aktuálně zobrazené** fronty (ne všech
  najednou — zbytečné I/O). Obrazovka si drží v paměti cache na frontu
  (cesta k souboru, poslední offset, už vykreslené události), takže
  přepnutí zpět na dříve zobrazenou frontu nezačíná od nuly.
- Chybí-li transkript (fronta bez jediného běhu) → text "No conversation
  yet."
- Nová klávesa `c` na dashboardu otevře `ConversationsScreen`. `Esc` zpět,
  stejně jako ostatní obrazovky.

Vizuální styl (první verze, doladíme naživo v tmuxu po implementaci —
rychlejší smyčka než popisovat barvy textem): tmavé pozadí, boxy zpráv s
azurovým okrajem, odlišená barva popisku odesílatele (člověk vs. Claude),
vybraný řádek v levém panelu zvýrazněný plnou barvou (stejný vzor jako
`DataTable` kurzor na dashboardu už dnes používá).

## Testování

- `transcript.py`: syntetické JSONL fixture pokrývající každé pravidlo
  filtrování (lidský text, text Clauda, tool_use, thinking-přeskočeno,
  syntetický tool-result "user" řádek-přeskočeno, nekompletní poslední
  řádek, inkrementální čtení od uloženého offsetu) + fixture ze skutečně
  zachyceného transkriptu z dřívějšího live testu (`LIVEDELIVERY`) jako
  regresní pojistka proti reálnému tvaru dat.
- `ConversationsScreen`: TUI test s dočasným transkript souborem — ověří
  vykreslení, přepnutí fronty šipkou překreslí pravý panel, chybějící
  transkript ukáže placeholder.
- Ruční ověření vzhledu: `capture-pane` v izolované tmux session (stejný
  postup jako u analytiky/gauge bugu) — obrazovka se přímo ukáže uživateli
  ke schválení barev/rozvržení.

## Vědomé zjednodušení (YAGNI)

- Žádné nástroj-specifické formátování `tool_call` náhledu (jeden obecný
  ořezaný text pro všechny nástroje).
- Žádná stránkování/omezení délky pro extrémně dlouhé konverzace v v1.
- Spodní panel beze změny stylu.
- Barevná paleta se doladí interaktivně po prvním buildu, ne dopředu v
  textu.
