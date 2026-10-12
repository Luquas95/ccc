# Remote control pro konverzace — návrh

Datum: 2026-10-13

## Ověřeno naživo (claude 2.1.296)

- `claude -p ... --remote-control x` přepínač tiše ignoruje (běh skončí,
  není k čemu se připojit).
- `claude remote-control --session-id` bere ID vzdálené session na
  serveru, ne lokální konverzace — nepoužitelné.
- Interaktivní `claude --resume <id> --remote-control <název>` ve skrytém
  tmux panelu převezme lokální session (stejné ID), vypíše
  „/remote-control is active · … https://claude.ai/code/session_…“ a
  `claude agents --json` ji hlásí `status: idle`.

## Chování

- Úvodní menu, skupina *cc-continue*: `Remote control (phone / claude.ai)`,
  **výchozí zaškrtnuto**. Nastavuje se jen při založení.
- Taková konverzace má `delivery_mode = remote_control`. Démon pro ni drží
  interaktivního Clauda v tmuxu `-L cc-continue-sessions`, session `q<id>`:
  `claude <session> --remote-control <název> <launch_flags>`, kde
  `<session>` je `first_run_flags` (fork / from-PR), jinak `--resume <id>`
  když přepis existuje, jinak `--session-id <id>`.
- Démon proces spustí, když neběží (po založení, restartu démona, pádu či
  `/exit`). Archivace ho ukončí (archivovaná RC konverzace se nezpracovává),
  smazání také.
- Po startu démon z panelu: potvrdí dotaz na důvěru složky (Enter),
  přečte odkaz `https://claude.ai/code/session_…` → `queues.remote_control_url`,
  a u fork / from-PR převezme skutečné ID session (`claude agents` podle
  PID panelu) → `set_queue_session`.
- Doručení položky fronty: počká, až session hlásí `status == idle`, vloží
  text přes tmux bracketed paste (`load-buffer` + `paste-buffer -p`, aby
  víceřádkový text nebyl odeslán po řádcích) a pošle Enter. Běh se zapíše
  jako `success` „Delivered to the remote-control session“ (bez tokenů).
- Limity: před doručením kontrola využití jako u headless. Když session
  přejde do `state == "blocked"` (limit uprostřed práce), démon vloží na
  začátek fronty pokračovací zprávu (continue text) a frontu přepne do
  `waiting_retry` (auto-continue) / `paused_limit`, čas resetu z využití
  (jinak +15 min). Doručuje se pak jen podle `status == idle`.
- TUI: hlavička konverzace a detail fronty ukazují `remote control` +
  odkaz. Ostatní (fronta úkolů, `r`, ikony) beze změny.

## Komponenty

- `managed_sessions.py`: tmux socket, `build_interactive_command`,
  `is_running`, `start`, `stop`, `capture`, `pane_pid`, `paste_and_submit`,
  `parse_remote_url`, `needs_trust_confirmation`. Všechna volání tmuxu přes
  `_run` (v testech podstrčené).
- Storage: `remote_control_url` sloupec + setter, `add_queue_item_front`.
- Orchestrátor: údržba procesu a doručování pro `remote_control`.
- `start_conversation(remote_control=...)`, okno New conversation, hlavička.

## Testy

Čisté funkce (příkaz, URL, trust), `_run` volání (start/stop/paste),
orchestrátor s podstrčenými `managed_sessions` a `discover_sessions`
(spuštění, doručení až při idle, blocked → continue + čekání, archivace →
stop, smazání → stop, převzetí ID), storage, TUI checkbox + hlavička.
Ruční ověření naživo s Haiku.
