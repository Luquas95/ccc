# Preset prompty — návrh

Datum: 2026-10-15. Schváleno uživatelem v konverzaci (volby A u všech otázek,
lišta pod polem pro zprávu).

## Cíl

Často používané prompty si uživatel uloží v Settings a v konverzaci je vloží
nebo rovnou odešle klávesou `Alt+1` … `Alt+9`.

## Data

- `src/ccc/prompt_presets.py`: `PromptPreset(name: str, text: str, send_now: bool)`,
  `load_prompt_presets(storage) -> list[PromptPreset]`,
  `save_prompt_presets(storage, presets)`. Ukládá se jako JSON seznam do
  tabulky `settings` pod klíčem `prompt_presets`. `MAX_PRESETS = 9`.
- Poškozený JSON nebo neplatné položky (chybí název/text) se při načtení
  přeskočí; načte se nejvýš 9 položek. Bez migrace DB.

## Settings (Ctrl+P)

- Nová sekce **Preset prompts** (mezi Queues a New-conversation presets):
  tabulka se sloupci *Key* (`Alt+N`), *Mode* (`⏎ send` / `✎ insert`),
  *Name*, *Prompt* (první řádek, zkrácený).
- Tlačítka *Add*, *Edit*, *Delete*, *Up*, *Down*. *Add* je vypnuté při 9
  presetech; Enter na řádku = *Edit*.
- *Add/Edit* otevře `PromptPresetModal`: pole Name (Input), Prompt
  (TextArea, víceřádkový), Checkbox „Send right away (with Enter)“.
  `Ctrl+S` uloží, `Esc` zruší. Prázdný název nebo prompt → chybová hláška,
  okno zůstane otevřené.
- Seznam se upravuje v paměti formuláře a do DB se zapíše až při *Save*
  Settings (Cancel ho zahodí), stejně jako ostatní pole formuláře.

## Konverzace

- Pod polem pro zprávu (`#message-input`) lišta `#prompt-presets-bar`:
  `Alt+1 ⏎ Pokračuj   Alt+2 ✎ Zkontroluj soubor …` — `⏎` rovnou odeslat,
  `✎` jen vložit. Bez presetů je skrytá. Položky jsou klikací (stejný efekt
  jako klávesa).
- Klávesy `alt+1` … `alt+9` na `ConversationsScreen` (priority, fungují i
  při psaní; ve footeru skryté, v nápovědě `?` uvedené).
  - `✎` (send_now = False): vloží text na pozici kurzoru do pole zprávy a
    přesune do něj fokus.
  - `⏎` (send_now = True): odešle jen text presetu do vybrané konverzace
    (stejná cesta jako Enter — přidá úkol do fronty, z `paused_limit`
    přepne na `idle`); rozepsaný text v poli zůstane.
  - Neexistující preset → notifikace „No preset on Alt+N — add one in
    Settings (Ctrl+P)“. Žádná vybraná konverzace → notifikace.
- Lišta se obnoví po zavření Settings (`on_screen_resume`).

## Testy

- `tests/test_prompt_presets.py`: uložení/načtení, poškozený JSON, limit 9.
- `tests/test_tui_prompt_presets.py`: Settings přidá/upraví/smaže/posune a
  uloží až po Save; lišta ukazuje presety a je skrytá bez nich; Alt+N vloží
  na kurzor; Alt+N s ⏎ přidá úkol a nechá rozepsaný text; chybějící preset.
