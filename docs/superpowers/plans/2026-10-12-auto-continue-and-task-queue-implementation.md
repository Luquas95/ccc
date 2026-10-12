# Auto-continue & Task Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-conversation auto-continue after usage limits, reset detection from the usage API, and a task-queue editor in the TUI.

**Architecture:** A pure `limits` module turns `ProUsage` into "wait until" times. The queue runtime loop becomes state-driven: it honours persisted `waiting_retry`/`paused_limit` + `next_retry_at`, checks usage before starting an item, and on 429 decides between auto-retry and pause per `auto_continue`. Interrupted items are retried with a configurable continue text. A `TasksModal` edits pending items.

**Tech Stack:** Python 3.12, Textual 8.2.8, SQLite, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-10-12-auto-continue-and-task-queue-design.md`

## Global Constraints

- Existing queues keep today's behaviour (`auto_continue` defaults to 1, `paused` to 0).
- Tests never hit the network: autouse fixture in `tests/conftest.py` patches `cc_continue.orchestrator.get_pro_usage` to return `None`.
- Arbitrary text never goes through markup: `Content`/`Text`, never f-string markup.
- Default continue text: `Pokračuj tam, kde jsi skončil.`
- Run tests with `.venv/bin/python -m pytest -q`.

---

### Task 1: `limits` module

**Files:** Create `src/cc_continue/limits.py`; Test `tests/test_limits.py`

**Produces:** `RESET_BUFFER = timedelta(seconds=30)`; `exhausted_until(usage: ProUsage | None, now: datetime) -> datetime | None`; `retry_time_after_rate_limit(usage: ProUsage | None, now: datetime) -> datetime | None`. `now` and results are naive local datetimes.

- [ ] Tests: no usage → None (both); nothing ≥100 → `exhausted_until` None; 5h at 100 → its reset + 30 s (local naive); 5h and weekly both at 100 → the later; per-model window at 100 counts; reset in the past → None; after 429 picks highest-utilization window even below 100; after 429 with reset in the past → None.
- [ ] Implement:

```python
def _windows(usage):
    if usage is None:
        return []
    found = [w for w in (usage.five_hour, usage.seven_day) if w is not None]
    return found + list(usage.per_model)

def _local(dt):
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt

def exhausted_until(usage, now):
    resets = [_local(w.resets_at) + RESET_BUFFER for w in _windows(usage) if w.utilization_pct >= 100]
    resets = [r for r in resets if r > now]
    return max(resets) if resets else None

def retry_time_after_rate_limit(usage, now):
    windows = _windows(usage)
    if not windows:
        return None
    busiest = max(windows, key=lambda w: w.utilization_pct)
    at = _local(busiest.resets_at) + RESET_BUFFER
    return at if at > now else None
```

- [ ] Commit `feat: derive usage-limit wait times from the usage API`

### Task 2: Storage & models

**Files:** `models.py`, `storage.py`; Test `tests/test_storage.py`

**Produces:** `QueueStatus.PAUSED_LIMIT = "paused_limit"`; `Queue.auto_continue: bool = True`, `Queue.paused: bool = False`; `QueueItem.continue_on_retry: bool = False`; `Storage.create_queue(..., auto_continue: bool = True)`; `set_queue_auto_continue(queue_id, value: bool)`; `set_queue_paused(queue_id, value: bool)`; `set_item_continue_on_retry(item_id, value: bool)`; `update_item_text(item_id, text)`; `skip_item(item_id)` (→ `ItemStatus.SKIPPED`); `move_item(item_id, delta: int) -> bool` (swap `position` with the neighbouring *pending* item of the same queue; False at the edge); `get_setting(key, default=None) -> str | None`; `set_setting(key, value)`.

- [ ] Tests: defaults on new and migrated DBs; each setter round-trips; `move_item` up/down/edge with a non-pending item in between ignored; `skip_item` removes from `list_pending_items`; settings default/overwrite.
- [ ] Implement (schema columns + migration in `_migrate_add_always_resume_column`, `settings` table in `SCHEMA`, row mappers).
- [ ] Commit `feat: storage for auto-continue, queue pause, task editing and settings`

### Task 3: Orchestrator — state-driven loop, usage gating, continue text

**Files:** `orchestrator.py`, `transcript.py`, `tests/conftest.py`; Test `tests/test_orchestrator.py`, `tests/test_transcript.py`

**Consumes:** Tasks 1–2. **Produces:** `transcript.last_human_text(session_id) -> str | None`; `DEFAULT_CONTINUE_TEXT`; orchestrator imports `get_pro_usage` at module level (patchable).

Loop per iteration:

```python
queue = storage.get_queue(id)
if queue.status in (BLOCKED_ERROR, PAUSED_LIMIT) or queue.paused: wait POLL; continue
if queue.status == WAITING_RETRY and queue.next_retry_at:
    remaining = (queue.next_retry_at - now).total_seconds()
    if remaining > 0: wait min(remaining, POLL); continue
    until = exhausted_until(await to_thread(get_pro_usage, True), now)
    if until: update_queue_status(WAITING_RETRY, next_retry_at=until); continue
    update_queue_status(IDLE)
if storage.next_pending_item(id) is None: set IDLE (if not already); wait POLL; continue
until = exhausted_until(await to_thread(get_pro_usage), now)   # headless only
if until: _hold_for_limit(queue, until); continue
item = claim_next_pending_item(...)
...
```

`_hold_for_limit(queue, until)`: status `WAITING_RETRY` if `queue.auto_continue` else `PAUSED_LIMIT`, `next_retry_at=until`.

Headless `_process_item`: `text = continue_text if item.continue_on_retry else item.prompt_text`; run with `text`; `PromptRun.prompt_text = text`. On `RATE_LIMITED`: item → pending; if `last_human_text(queue.session_id)` equals `text` (stripped) → `set_item_continue_on_retry(item.id, True)`; `retry_at = retry_time_after_rate_limit(await to_thread(get_pro_usage, True), now) or parse_reset_time(...) or backoff`; `_hold_for_limit(queue, retry_at)`; return (no in-place sleep).

- [ ] conftest autouse fixture: `monkeypatch.setattr("cc_continue.orchestrator.get_pro_usage", lambda force_refresh=False: None)`.
- [ ] Tests: auto on → waiting_retry then runs again with continue text when transcript shows the prompt; auto off → paused_limit, no second run until status set idle; transcript without the prompt → original text resent; usage exhausted before start → no run, waiting_retry with the reset; paused queue doesn't run; waiting_retry with future `next_retry_at` restored after restart isn't run early; `last_human_text`.
- [ ] Commit `feat: auto-continue per conversation with usage-based reset detection`

### Task 4: CLI `config continue-text`

**Files:** `cli.py`; Test `tests/test_cli.py`

- [ ] `cc-continue config continue-text [VALUE]` — with VALUE sets, without prints current (default if unset).
- [ ] Commit `feat: cc-continue config continue-text`

### Task 5: TUI — Tasks editor, status lines, auto-continue checkbox

**Files:** Create `tui/tasks.py`; modify `tui/conversations.py`, `tui/new_conversation.py`, `tui/layout.py` (status style), `orchestrator.start_conversation(auto_continue=True)`; Tests `tests/test_tui_tasks.py`, `tests/test_tui_conversations.py`, `tests/test_tui_new_conversation.py`

**Produces:** `TaskEditModal(text: str = "", title: str = "New task")` → dismiss `str | None` (`#task-text` TextArea, `ctrl+s` save, `escape` cancel); `TasksModal(storage, queue_id)` (`#tasks-state` Static, `#tasks-table` DataTable; bindings a/e/enter/delete/ctrl+up/ctrl+down/p/o/escape).

- [ ] Conversations: binding `t` → `TasksModal`, re-render on close; header adds `auto-continue on/off`; status line: `PAUSED_LIMIT` before/after reset, `paused` queue; `r` also resumes `PAUSED_LIMIT`; sending a message while `PAUSED_LIMIT` sets `IDLE`.
- [ ] New conversation: `Checkbox("Auto-continue after usage limit", value=True, id="auto-continue")` under a "cc-continue" title; passed to `start_conversation`.
- [ ] Tests for every key in the Tasks modal, status line texts, `r` from paused_limit, checkbox off → queue `auto_continue` False.
- [ ] Commit `feat: task queue editor, auto-continue toggle and limit states in the TUI`

### Task 6: Docs & verification

- [ ] README: auto-continue, reset detection, Tasks editor keys, `config continue-text`.
- [ ] Screenshots of Tasks modal and paused status; restart services; full suite green.
- [ ] Commit `docs: auto-continue and task queue`
