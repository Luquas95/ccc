# Preset prompty — plán implementace

Spec: `docs/superpowers/specs/2026-10-15-prompt-presets-design.md`. Větev `prompt-presets`.

1. **Datový modul** — `src/ccc/prompt_presets.py` + `tests/test_prompt_presets.py`
   (TDD: testy load/save/poškozený JSON/limit → implementace → zelené).
2. **Editor presetu** — `PromptPresetModal` v `src/ccc/tui/prompt_presets.py`
   (Name, Prompt TextArea, Checkbox; Ctrl+S/Esc; validace), dismiss s
   `PromptPreset | None`.
3. **Sekce v Settings** — `src/ccc/tui/settings.py`: tabulka + tlačítka,
   práce se seznamem v paměti, zápis v `action_save`.
4. **Lišta a klávesy v konverzaci** — `src/ccc/tui/conversations.py`:
   `#prompt-presets-bar` pod `#message-input`, `alt+1..9` (priority,
   show=False), vyčlenit odesílání do `_enqueue_text()`, klik na položku,
   obnova v `on_screen_resume`.
5. **Nápověda a README** — `help.py` (`alt+1…9`, sekce editoru), README
   (Settings → Preset prompts, tabulka zkratek), screenshot conversations
   a settings přegenerovat (demo data s presety).
6. **Testy TUI** — `tests/test_tui_prompt_presets.py`; celá sada zelená.
7. **Ověření naživo** v běžícím TUI po restartu služby, pak
   finishing-a-development-branch (+ pr-description, pokud PR).
