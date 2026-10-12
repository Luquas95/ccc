# Archivace, mazání a stav konverzací v seznamu — návrh

Datum: 2026-10-12

## Archivace a mazání

- `queues.archived INTEGER NOT NULL DEFAULT 0`. Archivovaná konverzace se
  neukazuje v Conversations ani na Dashboardu; `h` v Conversations přepíná
  zobrazení archivovaných (šedě). Archivace nic nemaže a démon archivované
  fronty dál zpracovává.
- Conversations: `x` archivovat/obnovit vybranou konverzaci, `ctrl+d`
  smazat — potvrzovací okno (`ConfirmModal`, Enter/y = ano, Esc/n = ne).
- Smazání (`Storage.delete_queue`) odstraní řádky `run_model_usage`,
  `prompt_runs`, `queue_items` a `queues` dané fronty v jedné transakci.
  Přepis Claude Code v `~/.claude/projects` zůstává (session jde obnovit
  přes *Resume selected…*).
- Fronta ve stavu `running` smazat nejde: okno místo potvrzení ukáže
  „Claude is working on it — wait or pause it first“.
- Dashboard respektuje `archived` (skryté).
- Démon: `QueueRuntime._loop` skončí, když fronta v DB už neexistuje
  (`Storage.find_queue(id) -> Queue | None`); `Orchestrator` runtime pro
  smazanou frontu neobnovuje (seznam se bere z DB).

## Stav v seznamu konverzací

- `queues.last_seen_at TEXT NULL` — nastaví se při zobrazení konverzace
  v Conversations (`Storage.mark_seen(queue_id)`), a znovu při každém
  překreslení, kdy přibudou události u právě otevřené konverzace.
- „Nová odpověď“ = existuje běh fronty s `finished_at` > `last_seen_at`
  (nebo `last_seen_at` je NULL a nějaký běh existuje).
  `Storage.unseen_queue_ids() -> set[int]`.
- Ikona před jménem (čistá funkce `queue_marker(queue, unseen) -> tuple[str, str]`
  v `tui/layout.py`): `●` green = running; `⏸` magenta = paused_limit
  nebo waiting_retry, `⏸` yellow = paused; `✖` red = blocked_error;
  `◆` cyan = nová odpověď; jinak mezera. Za jménem `·N` čekajících úkolů
  (dim), je-li N > 0.
- Dashboard: stejná ikona před jménem projektu.
- Seznam v Conversations se při 2s obnovování překreslí, když se změní
  ikony/počty (ne jen sada front).

## Testy

Storage (archivace, delete kaskádově, mark_seen/unseen, find_queue),
orchestrátor (smazaná fronta ukončí runtime bez chyby), `queue_marker`,
TUI (`x`, `h`, `ctrl+d` potvrzení/zrušení/running, ikony a `·N`, `◆`
zmizí po otevření).
