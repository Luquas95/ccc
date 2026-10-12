# New Conversation Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the TUI start new Claude Code conversations — pick a directory, tick launch attributes (incl. resume/continue/fork/from-PR) — and chat with them inside the Conversations view.

**Architecture:** A new conversation is a new headless queue carrying its own `launch_flags` (sent on every run) and one-shot `first_run_flags` (fork / from-PR, cleared after the first successful run, when the daemon adopts the session id Claude Code returned). The daemon/runner pass these to `claude -p`. The TUI gets a `NewConversationModal` and a message input in Conversations.

**Tech Stack:** Python 3.12, Textual 8.2.8, SQLite, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-10-12-new-conversation-launcher-design.md`

## Global Constraints

- Legacy queues (`launch_flags IS NULL`) must keep running exactly as before: `--dangerously-skip-permissions`, `--session-id`/`--resume` as today.
- UI copy stays English, like the rest of the TUI.
- Fixed attribute list exactly as in the spec table (no config file).
- Anything user/model-provided interpolated into Rich markup must go through `rich.markup.escape`.
- Button labels use `(x)` not `[x]` (brackets are eaten as markup).
- Run tests with `.venv/bin/python -m pytest -q` from the repo root.

---

### Task 1: `launch_options` — attribute catalogue and flag building

**Files:**
- Create: `src/cc_continue/launch_options.py`
- Test: `tests/test_launch_options.py`

**Interfaces:**
- Produces: `GROUPS: tuple[OptionGroup, ...]`, `OptionGroup(key, title, options, exclusive, required)`, `LaunchOption(key, label, flags, short)`, constants `SESSION_NEW`, `SESSION_CONTINUE`, `SESSION_RESUME`, `SESSION_FROM_PR`, `FORK`, `DEFAULT_SELECTION: frozenset[str]`, `toggle(selection, key, checked) -> frozenset[str]`, `session_mode(selection) -> str`, `persistent_flags(selection) -> list[str]`, `describe_flags(flags: list[str] | None) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
from cc_continue.launch_options import (
    DEFAULT_SELECTION, FORK, SESSION_CONTINUE, SESSION_NEW, describe_flags,
    persistent_flags, session_mode, toggle,
)


def test_default_is_new_session_with_skip_permissions():
    assert session_mode(DEFAULT_SELECTION) == SESSION_NEW
    assert persistent_flags(DEFAULT_SELECTION) == ["--dangerously-skip-permissions"]


def test_exclusive_group_replaces_previous_choice():
    sel = toggle(DEFAULT_SELECTION, "model_opus", True)
    sel = toggle(sel, "model_sonnet", True)
    assert "model_opus" not in sel and "model_sonnet" in sel


def test_optional_exclusive_group_can_be_cleared():
    sel = toggle(DEFAULT_SELECTION, "effort_max", True)
    sel = toggle(sel, "effort_max", False)
    assert not any(k.startswith("effort_") for k in sel)


def test_required_group_cannot_be_emptied():
    sel = toggle(DEFAULT_SELECTION, "perm_skip", False)
    assert "perm_skip" in sel


def test_fork_only_with_a_resuming_session_mode():
    assert FORK not in toggle(DEFAULT_SELECTION, FORK, True)
    sel = toggle(toggle(DEFAULT_SELECTION, SESSION_CONTINUE, True), FORK, True)
    assert FORK in sel
    assert FORK not in toggle(sel, SESSION_NEW, True)


def test_persistent_flags_in_group_order_without_session_flags():
    sel = DEFAULT_SELECTION
    for key in ("model_opus", "effort_max", "other_chrome", SESSION_CONTINUE, FORK):
        sel = toggle(sel, key, True)
    assert persistent_flags(sel) == [
        "--dangerously-skip-permissions", "--model", "opus", "--effort", "max", "--chrome",
    ]


def test_describe_flags():
    assert describe_flags(None) == "legacy (skip permissions)"
    assert describe_flags(["--permission-mode", "plan", "--model", "haiku"]) == "plan only · Haiku"
    assert describe_flags(["--weird"]) == "--weird"
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest -q tests/test_launch_options.py` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
"""Fixed catalogue of attributes a new conversation can be started with,
and the pure logic turning a set of ticked keys into `claude` flags."""
from __future__ import annotations

from dataclasses import dataclass

SESSION_NEW = "session_new"
SESSION_CONTINUE = "session_continue"
SESSION_RESUME = "session_resume"
SESSION_FROM_PR = "session_from_pr"
FORK = "fork"


@dataclass(frozen=True)
class LaunchOption:
    key: str
    label: str
    flags: tuple[str, ...]
    short: str  # compact label for headers / queue detail


@dataclass(frozen=True)
class OptionGroup:
    key: str
    title: str
    options: tuple[LaunchOption, ...]
    exclusive: bool  # ticking one unticks the rest of the group
    required: bool  # exactly one must stay ticked


GROUPS: tuple[OptionGroup, ...] = (
    OptionGroup("session", "Session", (
        LaunchOption(SESSION_NEW, "New session", (), "new"),
        LaunchOption(SESSION_CONTINUE, "Continue last in directory", (), "continue"),
        LaunchOption(SESSION_RESUME, "Resume selected…", (), "resume"),
        LaunchOption(SESSION_FROM_PR, "From pull request…", (), "from PR"),
    ), exclusive=True, required=True),
    OptionGroup("session_extra", "", (
        LaunchOption(FORK, "As a copy (fork)", ("--fork-session",), "fork"),
    ), exclusive=False, required=False),
    OptionGroup("permissions", "Permissions", (
        LaunchOption("perm_skip", "Skip all permission checks", ("--dangerously-skip-permissions",), "skip permissions"),
        LaunchOption("perm_accept_edits", "Auto-accept edits", ("--permission-mode", "acceptEdits"), "accept edits"),
        LaunchOption("perm_plan", "Plan only", ("--permission-mode", "plan"), "plan only"),
    ), exclusive=True, required=True),
    OptionGroup("model", "Model", (
        LaunchOption("model_opus", "Opus", ("--model", "opus"), "Opus"),
        LaunchOption("model_sonnet", "Sonnet", ("--model", "sonnet"), "Sonnet"),
        LaunchOption("model_haiku", "Haiku", ("--model", "haiku"), "Haiku"),
        LaunchOption("model_fable", "Fable", ("--model", "fable"), "Fable"),
    ), exclusive=True, required=False),
    OptionGroup("effort", "Effort", (
        LaunchOption("effort_high", "high", ("--effort", "high"), "effort high"),
        LaunchOption("effort_xhigh", "xhigh", ("--effort", "xhigh"), "effort xhigh"),
        LaunchOption("effort_max", "max", ("--effort", "max"), "effort max"),
    ), exclusive=True, required=False),
    OptionGroup("other", "Other", (
        LaunchOption("other_fallback_sonnet", "Fallback to Sonnet when overloaded", ("--fallback-model", "sonnet"), "fallback Sonnet"),
        LaunchOption("other_chrome", "Claude in Chrome", ("--chrome",), "Chrome"),
        LaunchOption("other_safe_mode", "Safe mode (no customizations)", ("--safe-mode",), "safe mode"),
    ), exclusive=False, required=False),
)

# Groups whose choice decides WHICH session to talk to rather than adding
# flags to every run — handled by orchestrator.start_conversation().
SESSION_GROUP_KEYS = ("session", "session_extra")

DEFAULT_SELECTION: frozenset[str] = frozenset({SESSION_NEW, "perm_skip"})


def group_of(key: str) -> OptionGroup:
    for group in GROUPS:
        if any(o.key == key for o in group.options):
            return group
    raise KeyError(key)


def toggle(selection: frozenset[str], key: str, checked: bool) -> frozenset[str]:
    group = group_of(key)
    sel = set(selection)
    if checked:
        if group.exclusive:
            sel -= {o.key for o in group.options}
        sel.add(key)
    elif not group.required:
        sel.discard(key)
    if SESSION_NEW in sel:
        sel.discard(FORK)  # nothing to copy from
    return frozenset(sel)


def session_mode(selection: frozenset[str]) -> str:
    for option in GROUPS[0].options:
        if option.key in selection:
            return option.key
    return SESSION_NEW


def persistent_flags(selection: frozenset[str]) -> list[str]:
    flags: list[str] = []
    for group in GROUPS:
        if group.key in SESSION_GROUP_KEYS:
            continue
        for option in group.options:
            if option.key in selection:
                flags.extend(option.flags)
    return flags


def describe_flags(flags: list[str] | None) -> str:
    """Compact human summary of a queue's persistent flags."""
    if flags is None:
        return "legacy (skip permissions)"
    remaining = list(flags)
    parts: list[str] = []
    for group in GROUPS:
        if group.key in SESSION_GROUP_KEYS:
            continue
        for option in group.options:
            n = len(option.flags)
            for i in range(len(remaining) - n + 1):
                if tuple(remaining[i:i + n]) == option.flags:
                    parts.append(option.short)
                    del remaining[i:i + n]
                    break
    parts.extend(remaining)
    return " · ".join(parts) if parts else "default"
```

- [ ] **Step 4: Run tests** → PASS.
- [ ] **Step 5: Commit** `feat: fixed catalogue of launch attributes for new conversations`

---

### Task 2: Storage — launch columns and helper queries

**Files:**
- Modify: `src/cc_continue/models.py` (`Queue`), `src/cc_continue/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Produces: `Queue.launch_flags: list[str] | None = None`, `Queue.first_run_flags: list[str] | None = None`; `Storage.create_queue(..., launch_flags=None, first_run_flags=None)`; `Storage.set_queue_session(queue_id, session_id) -> None` (also clears `first_run_flags`, sets `always_resume=1`; raises `sqlite3.IntegrityError` if the id belongs to another queue); `Storage.recent_project_paths(limit=10) -> list[str]`; `Storage.list_pending_items(queue_id) -> list[QueueItem]`.

- [ ] **Step 1: Failing tests** (append to `tests/test_storage.py`)

```python
import sqlite3 as _sqlite3


def test_launch_flags_round_trip(tmp_path):
    storage = Storage(tmp_path / "h.db")
    q = storage.create_queue("a", "/tmp/a", "s1", launch_flags=["--model", "opus"], first_run_flags=["--fork-session"])
    q = storage.get_queue(q.id)
    assert q.launch_flags == ["--model", "opus"]
    assert q.first_run_flags == ["--fork-session"]
    assert storage.create_queue("b", "/tmp/b", "s2").launch_flags is None


def test_migration_adds_launch_columns_to_old_db(tmp_path):
    db = tmp_path / "old.db"
    conn = _sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE queues (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, project_path TEXT NOT NULL, "
        "session_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'idle', next_retry_at TEXT, last_error TEXT, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, always_resume INTEGER NOT NULL DEFAULT 0, "
        "delivery_mode TEXT NOT NULL DEFAULT 'headless')"
    )
    conn.execute("INSERT INTO queues (name, project_path, session_id, created_at, updated_at) VALUES ('x','/x','sx','2026-01-01T00:00:00','2026-01-01T00:00:00')")
    conn.commit(); conn.close()
    q = Storage(db).list_queues()[0]
    assert q.launch_flags is None and q.first_run_flags is None


def test_set_queue_session_adopts_id_and_clears_first_run(tmp_path):
    storage = Storage(tmp_path / "h.db")
    q = storage.create_queue("a", "/tmp/a", "placeholder", first_run_flags=["--fork-session"])
    storage.set_queue_session(q.id, "real-id")
    q = storage.get_queue(q.id)
    assert (q.session_id, q.first_run_flags, q.always_resume) == ("real-id", None, True)


def test_set_queue_session_collision_raises(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.create_queue("a", "/tmp/a", "taken")
    q = storage.create_queue("b", "/tmp/b", "placeholder")
    with pytest.raises(_sqlite3.IntegrityError):
        storage.set_queue_session(q.id, "taken")


def test_recent_project_paths_and_pending_items(tmp_path):
    storage = Storage(tmp_path / "h.db")
    a = storage.create_queue("a", "/tmp/a", "s1")
    storage.create_queue("b", "/tmp/b", "s2")
    storage.create_queue("a2", "/tmp/a", "s3")
    storage.update_queue_status(a.id, QueueStatus.IDLE)  # bumps updated_at
    assert storage.recent_project_paths()[0] == "/tmp/a"
    assert set(storage.recent_project_paths()) == {"/tmp/a", "/tmp/b"}
    storage.add_queue_item(a.id, "one"); storage.add_queue_item(a.id, "two")
    assert [i.prompt_text for i in storage.list_pending_items(a.id)] == ["one", "two"]
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**
  - `models.Queue`: add the two fields (default `None`).
  - `storage.SCHEMA` queues table: add `launch_flags TEXT,` and `first_run_flags TEXT` columns.
  - `_migrate_add_always_resume_column`: also `ALTER TABLE queues ADD COLUMN launch_flags TEXT` / `first_run_flags TEXT` when missing.
  - `create_queue(..., launch_flags: list[str] | None = None, first_run_flags: list[str] | None = None)`: insert `json.dumps(x) if x is not None else None`.
  - `_row_to_queue`: `json.loads(row["launch_flags"]) if row["launch_flags"] else None` (same for first_run).
  - New methods:

```python
    def set_queue_session(self, queue_id: int, session_id: str) -> None:
        """Adopt the session id Claude Code actually used (fork / from-PR
        first runs return a new one). Clears the one-shot first-run flags;
        later runs plain --resume it."""
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE queues SET session_id = ?, first_run_flags = NULL, always_resume = 1, updated_at = ? WHERE id = ?",
                (session_id, datetime.now().isoformat(), queue_id),
            )
            conn.commit()

    def recent_project_paths(self, limit: int = 10) -> list[str]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT project_path, MAX(updated_at) AS last FROM queues GROUP BY project_path ORDER BY last DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [r["project_path"] for r in rows]

    def list_pending_items(self, queue_id: int) -> list[QueueItem]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM queue_items WHERE queue_id = ? AND status = ? ORDER BY position",
                (queue_id, ItemStatus.PENDING.value),
            ).fetchall()
            return [self._row_to_item(r) for r in rows]
```

- [ ] **Step 4: Run** → PASS (whole suite too).
- [ ] **Step 5: Commit** `feat: store launch flags and first-run flags per queue`

---

### Task 3: Runner — build the `claude` command from queue flags

**Files:**
- Modify: `src/cc_continue/runner.py`, every fake `run_fn` in `tests/test_orchestrator.py`, `tests/test_daemon.py`
- Test: `tests/test_runner_command.py`

**Interfaces:**
- Produces: `build_command(session_id, prompt, resume, launch_flags=None, first_run_flags=None) -> list[str]`; `execute(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None)`; `RunFn = Callable[[str, str, str, bool, list[str] | None, list[str] | None], Awaitable[RunResult]]`.

- [ ] **Step 1: Failing tests**

```python
from cc_continue.runner import build_command


def test_legacy_queue_command_unchanged():
    assert build_command("sid", "hi", False) == [
        "claude", "--session-id", "sid", "-p", "hi", "--output-format", "json", "--dangerously-skip-permissions",
    ]
    assert build_command("sid", "hi", True)[1:3] == ["--resume", "sid"]


def test_launch_flags_replace_legacy_permission_flag():
    cmd = build_command("sid", "hi", True, ["--permission-mode", "plan", "--model", "haiku"])
    assert "--dangerously-skip-permissions" not in cmd
    assert cmd[-4:] == ["--permission-mode", "plan", "--model", "haiku"]


def test_first_run_flags_that_pick_the_session_drop_own_session_flag():
    cmd = build_command("placeholder", "hi", False, [], ["--resume", "orig", "--fork-session"])
    assert cmd[:4] == ["claude", "--resume", "orig", "--fork-session"]
    assert "placeholder" not in cmd
    cmd = build_command("placeholder", "hi", False, [], ["--from-pr", "42"])
    assert cmd[:3] == ["claude", "--from-pr", "42"] and "placeholder" not in cmd
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** in `runner.py`:

```python
# Flags used for queues created before launch attributes existed (NULL
# launch_flags) — exactly what every run used before.
LEGACY_FLAGS = ["--dangerously-skip-permissions"]

# First-run flags that themselves say which session to talk to.
_SESSION_SELECTING_FLAGS = ("--resume", "--from-pr")


def build_command(session_id, prompt, resume, launch_flags=None, first_run_flags=None) -> list[str]:
    first = list(first_run_flags or [])
    if any(f in first for f in _SESSION_SELECTING_FLAGS):
        session_flag: list[str] = []
    else:
        session_flag = ["--resume", session_id] if resume else ["--session-id", session_id]
    flags = LEGACY_FLAGS if launch_flags is None else list(launch_flags)
    return ["claude", *session_flag, *first, "-p", prompt, "--output-format", "json", *flags]
```

and `execute(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None)` runs `*build_command(...)`. Update fakes: `sed -i 's/(project_path, session_id, prompt, resume):/(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):/'` in the two test files; `RunFn` in orchestrator gets the two extra params.

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: runner builds claude command from per-queue launch flags`

---

### Task 4: Orchestrator — start conversations, first-run session adoption

**Files:**
- Modify: `src/cc_continue/orchestrator.py`
- Test: `tests/test_orchestrator.py` (append)

**Interfaces:**
- Consumes: Task 1 (`session_mode`, `persistent_flags`, constants), Task 2 storage methods, Task 5 `list_sessions_for_directory` (import from `cc_continue.transcript`; write Task 5 first if executing out of order).
- Produces: `start_conversation(storage, project_path, selection, *, name=None, session_id=None, pr=None) -> Queue` (raises `ValueError` with a user-facing message).

- [ ] **Step 1: Failing tests**

```python
from cc_continue.launch_options import DEFAULT_SELECTION, FORK, SESSION_CONTINUE, SESSION_FROM_PR, SESSION_RESUME, toggle
from cc_continue.orchestrator import start_conversation


def test_start_new_conversation_creates_fresh_queue_per_launch(storage, project_dir):
    a = start_conversation(storage, str(project_dir), toggle(DEFAULT_SELECTION, "model_haiku", True))
    b = start_conversation(storage, str(project_dir), DEFAULT_SELECTION, name="second")
    assert a.id != b.id and a.session_id != b.session_id
    assert a.launch_flags == ["--dangerously-skip-permissions", "--model", "haiku"]
    assert not a.always_resume and a.first_run_flags is None and b.name == "second"


def test_start_rejects_missing_directory(storage, tmp_path):
    with pytest.raises(ValueError):
        start_conversation(storage, str(tmp_path / "nope"), DEFAULT_SELECTION)


def test_resume_reuses_existing_queue_unless_fork(storage, project_dir):
    sel = toggle(DEFAULT_SELECTION, SESSION_RESUME, True)
    first = start_conversation(storage, str(project_dir), sel, session_id="abc")
    assert first.always_resume and first.session_id == "abc"
    assert start_conversation(storage, str(project_dir), sel, session_id="abc").id == first.id
    fork = start_conversation(storage, str(project_dir), toggle(sel, FORK, True), session_id="abc")
    assert fork.id != first.id and fork.first_run_flags == ["--resume", "abc", "--fork-session"]


def test_continue_picks_latest_session_of_directory(storage, project_dir, monkeypatch):
    from cc_continue.transcript import SessionSummary
    from datetime import datetime
    monkeypatch.setattr("cc_continue.orchestrator.list_sessions_for_directory",
                        lambda path: [SessionSummary("newest", datetime.now(), "hi", 2)])
    q = start_conversation(storage, str(project_dir), toggle(DEFAULT_SELECTION, SESSION_CONTINUE, True))
    assert q.session_id == "newest"
    monkeypatch.setattr("cc_continue.orchestrator.list_sessions_for_directory", lambda path: [])
    with pytest.raises(ValueError):
        start_conversation(storage, str(project_dir), toggle(DEFAULT_SELECTION, SESSION_CONTINUE, True), name="x")


def test_from_pr_needs_value(storage, project_dir):
    sel = toggle(DEFAULT_SELECTION, SESSION_FROM_PR, True)
    with pytest.raises(ValueError):
        start_conversation(storage, str(project_dir), sel, pr="  ")
    q = start_conversation(storage, str(project_dir), sel, pr="42")
    assert q.first_run_flags == ["--from-pr", "42"]


async def test_first_run_adopts_returned_session_id(storage, project_dir):
    q = start_conversation(storage, str(project_dir),
                           toggle(toggle(DEFAULT_SELECTION, SESSION_RESUME, True), FORK, True), session_id="orig")
    storage.add_queue_item(q.id, "hello")
    calls = []

    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        calls.append((session_id, first_run_flags, launch_flags))
        return RunResult(status=RunStatus.SUCCESS, session_id="forked-id")

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    await asyncio.sleep(0.3)
    await orch.stop_all()
    assert calls[0][1] == ["--resume", "orig", "--fork-session"]
    q = storage.get_queue(q.id)
    assert q.session_id == "forked-id" and q.first_run_flags is None and q.always_resume
```

(`RunResult`, `RunStatus`, `Orchestrator`, `asyncio` are already imported at the top of `tests/test_orchestrator.py`; add any that are missing.)

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**
  - `RunFn` type gets the two list params; `_process_item` calls `self.run_fn(queue.project_path, queue.session_id, item.prompt_text, resume, queue.launch_flags, queue.first_run_flags)`.
  - On `SUCCESS`, after marking the item done:

```python
            if queue.first_run_flags is not None:
                adopted = result.session_id or queue.session_id
                try:
                    self.storage.set_queue_session(queue.id, adopted)
                except sqlite3.IntegrityError:
                    self.storage.update_queue_status(
                        queue.id, QueueStatus.BLOCKED_ERROR,
                        last_error=f"session {adopted} already has a conversation in cc-continue",
                    )
```

  - `start_conversation`:

```python
def start_conversation(storage, project_path, selection, *, name=None, session_id=None, pr=None) -> Queue:
    """Create the queue behind a conversation started from the TUI's
    New conversation dialog (see launch_options for what selection
    holds). Raises ValueError with a message fit to show the user."""
    if not Path(project_path).is_dir():
        raise ValueError(f"'{project_path}' is not an existing directory")
    mode = session_mode(selection)
    fork = FORK in selection and mode != SESSION_NEW
    flags = persistent_flags(selection)
    name = (name or "").strip() or Path(project_path).name or project_path

    if mode == SESSION_NEW:
        return storage.create_queue(name, project_path, str(uuid.uuid4()), launch_flags=flags)

    if mode == SESSION_FROM_PR:
        pr = (pr or "").strip()
        if not pr:
            raise ValueError("Enter a pull request number or URL.")
        first = ["--from-pr", pr] + (["--fork-session"] if fork else [])
        return storage.create_queue(name, project_path, str(uuid.uuid4()), launch_flags=flags, first_run_flags=first)

    if mode == SESSION_CONTINUE:
        sessions = list_sessions_for_directory(project_path)
        if not sessions:
            raise ValueError("There is no previous conversation in this directory.")
        session_id = sessions[0].session_id
    if not session_id:
        raise ValueError("Select a conversation to resume.")

    if fork:
        return storage.create_queue(
            name, project_path, str(uuid.uuid4()), launch_flags=flags,
            first_run_flags=["--resume", session_id, "--fork-session"],
        )
    existing = storage.get_queue_by_session_id(session_id)
    if existing is not None:
        return existing
    return storage.create_queue(name, project_path, session_id, always_resume=True, launch_flags=flags)
```

- [ ] **Step 4: Run** → PASS (full suite).
- [ ] **Step 5: Commit** `feat: start conversations with launch attributes; adopt forked session ids`

---

### Task 5: `list_sessions_for_directory`

**Files:**
- Modify: `src/cc_continue/transcript.py`
- Test: `tests/test_transcript.py` (append)

**Interfaces:**
- Produces: `SessionSummary(session_id: str, modified: datetime, first_prompt: str, message_count: int)`, `encode_project_dir(path: str) -> str`, `list_sessions_for_directory(path: str, limit: int = 50) -> list[SessionSummary]` (newest first, sessions without any human message skipped).

- [ ] **Step 1: Failing tests**

```python
import os
import time

from cc_continue.transcript import encode_project_dir, list_sessions_for_directory


def _line(kind, content, ts="2026-10-12T10:00:00.000Z"):
    if kind == "user":
        return json.dumps({"type": "user", "message": {"role": "user", "content": content}, "timestamp": ts}) + "\n"
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": content}]}, "timestamp": ts}) + "\n"


def test_encode_project_dir():
    assert encode_project_dir("/mnt/AI/DEV/CC-continue") == "-mnt-AI-DEV-CC-continue"
    assert encode_project_dir("/a/b_c.d") == "-a-b-c-d"


def test_lists_sessions_newest_first_via_path_and_realpath(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", root)
    real = tmp_path / "real"; real.mkdir()
    link = tmp_path / "link"; link.symlink_to(real)
    d1 = root / encode_project_dir(str(link)); d1.mkdir(parents=True)
    d2 = root / encode_project_dir(str(real)); d2.mkdir(parents=True)
    (d1 / "old.jsonl").write_text(_line("user", "first old") + _line("assistant", "ok"))
    time.sleep(0.01)
    (d2 / "new.jsonl").write_text(_line("user", "<command-name>x</command-name>") + _line("user", "real prompt"))
    (d2 / "empty.jsonl").write_text(_line("assistant", "no human"))
    os.utime(d1 / "old.jsonl", (1, 1))
    sessions = list_sessions_for_directory(str(link))
    assert [s.session_id for s in sessions] == ["new", "old"]
    assert sessions[0].first_prompt == "real prompt"
    assert sessions[1].message_count == 2
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**

```python
@dataclass
class SessionSummary:
    session_id: str
    modified: datetime
    first_prompt: str
    message_count: int


def encode_project_dir(path: str) -> str:
    """Claude Code's transcript directory name for a cwd: every
    non-alphanumeric character becomes "-" (confirmed on this machine)."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def list_sessions_for_directory(path: str, limit: int = 50) -> list[SessionSummary]:
    """Claude Code sessions recorded for a directory, newest first. Tries
    the path as given AND its realpath — ~/DEV is a symlink, and sessions
    started from either spelling land in different directories."""
    files: dict[str, Path] = {}
    for candidate in {path.rstrip("/") or "/", os.path.realpath(path)}:
        project_dir = PROJECTS_ROOT / encode_project_dir(candidate)
        if project_dir.is_dir():
            for f in project_dir.glob("*.jsonl"):
                files.setdefault(f.stem, f)
    newest = sorted(files.values(), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    summaries = []
    for f in newest:
        first_prompt, count = _summarize(f)
        if first_prompt is None:
            continue
        summaries.append(SessionSummary(f.stem, datetime.fromtimestamp(f.stat().st_mtime), first_prompt, count))
    return summaries


def _summarize(path: Path) -> tuple[str | None, int]:
    first_prompt = None
    count = 0
    with open(path, "rb") as fh:
        for raw in fh:
            if b'"type":"user"' not in raw and b'"type":"assistant"' not in raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for event in _events_from_line(data):
                if event.kind == "tool_call":
                    continue
                count += 1
                # Skip harness-injected lines like <command-name>…</command-name>.
                if first_prompt is None and event.kind == "human" and not event.text.lstrip().startswith("<"):
                    first_prompt = event.text.strip().splitlines()[0][:120]
    return first_prompt, count
```

(add `import os`, `import re` at the top.)

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: list a directory's past Claude Code sessions`

---

### Task 6: `NewConversationModal`

**Files:**
- Create: `src/cc_continue/tui/new_conversation.py`
- Test: `tests/test_tui_new_conversation.py`

**Interfaces:**
- Consumes: `launch_options` (Task 1), `start_conversation` (Task 4), `list_sessions_for_directory` (Task 5), `Storage.recent_project_paths` (Task 2), `layout.MODAL_CSS`.
- Produces: `NewConversationModal(storage, browse_root: Path | None = None)`; dismisses with the new/selected queue id (`int`) or `None`. Widget ids: `#recent-dirs` (OptionList), `#dir-tree` (DirectoryTree), `#launch-path` (Input), `#opt-<key>` (Checkbox per option), `#resume-sessions` (OptionList), `#from-pr-input` (Input), `#launch-name` (Input), `#launch-error` (Static), `#launch-start`, `#launch-cancel` (Buttons).

- [ ] **Step 1: Failing tests**

```python
import pytest
from textual.app import App
from textual.widgets import Checkbox, Input, OptionList

from cc_continue.storage import Storage
from cc_continue.tui.new_conversation import NewConversationModal


def _host(modal, results):
    class Host(App):
        async def on_mount(self):
            await self.push_screen(modal, results.append)
    return Host()


@pytest.mark.asyncio
async def test_start_creates_queue_with_ticked_flags(tmp_path):
    storage = Storage(tmp_path / "h.db")
    project = tmp_path / "proj"; project.mkdir()
    results = []
    app = _host(NewConversationModal(storage, browse_root=tmp_path), results)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one("#launch-path", Input).value = str(project)
        app.screen.query_one("#opt-model_haiku", Checkbox).value = True
        await pilot.pause()
        await pilot.click("#launch-start")
        await pilot.pause()
    queue = storage.get_queue(results[0])
    assert queue.project_path == str(project)
    assert queue.launch_flags == ["--dangerously-skip-permissions", "--model", "haiku"]


@pytest.mark.asyncio
async def test_exclusive_checkboxes_untick_each_other(tmp_path):
    app = _host(NewConversationModal(Storage(tmp_path / "h.db"), browse_root=tmp_path), [])
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one("#opt-model_opus", Checkbox).value = True
        await pilot.pause()
        app.screen.query_one("#opt-model_sonnet", Checkbox).value = True
        await pilot.pause()
        assert app.screen.query_one("#opt-model_opus", Checkbox).value is False
        assert app.screen.query_one("#opt-fork", Checkbox).disabled


@pytest.mark.asyncio
async def test_bad_path_shows_error_and_creates_nothing(tmp_path):
    storage = Storage(tmp_path / "h.db")
    results = []
    app = _host(NewConversationModal(storage, browse_root=tmp_path), results)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one("#launch-path", Input).value = str(tmp_path / "missing")
        await pilot.click("#launch-start")
        await pilot.pause()
        assert "not an existing directory" in str(app.screen.query_one("#launch-error").render())
    assert results == [] and storage.list_queues() == []


@pytest.mark.asyncio
async def test_recent_directory_fills_path(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.create_queue("a", str(tmp_path), "s1")
    app = _host(NewConversationModal(storage, browse_root=tmp_path), [])
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        recent = app.screen.query_one("#recent-dirs", OptionList)
        recent.highlighted = 0
        recent.action_select()
        await pilot.pause()
        assert app.screen.query_one("#launch-path", Input).value == str(tmp_path)


@pytest.mark.asyncio
async def test_resume_lists_sessions_of_path(tmp_path, monkeypatch):
    from datetime import datetime
    from cc_continue.transcript import SessionSummary
    monkeypatch.setattr("cc_continue.tui.new_conversation.list_sessions_for_directory",
                        lambda p: [SessionSummary("sid-1", datetime(2026, 10, 1, 9, 0), "fix the bug", 4)])
    storage = Storage(tmp_path / "h.db")
    results = []
    app = _host(NewConversationModal(storage, browse_root=tmp_path), results)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one("#launch-path", Input).value = str(tmp_path)
        app.screen.query_one("#opt-session_resume", Checkbox).value = True
        await pilot.pause()
        sessions = app.screen.query_one("#resume-sessions", OptionList)
        assert sessions.display and sessions.option_count == 1
        sessions.highlighted = 0
        await pilot.click("#launch-start")
        await pilot.pause()
    assert storage.get_queue(results[0]).session_id == "sid-1"
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `src/cc_continue/tui/new_conversation.py`:

```python
from __future__ import annotations

from pathlib import Path

from rich.markup import escape
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DirectoryTree, Input, OptionList, Static
from textual.widgets.option_list import Option

from cc_continue.launch_options import (
    DEFAULT_SELECTION, FORK, GROUPS, SESSION_FROM_PR, SESSION_NEW, SESSION_RESUME, session_mode, toggle,
)
from cc_continue.orchestrator import start_conversation
from cc_continue.storage import Storage
from cc_continue.transcript import list_sessions_for_directory
from cc_continue.tui.layout import MODAL_CSS


class _DirectoriesOnly(DirectoryTree):
    def filter_paths(self, paths):
        return [p for p in paths if p.is_dir() and not p.name.startswith(".")]


def default_browse_root() -> Path:
    dev = Path.home() / "DEV"
    return dev if dev.is_dir() else Path.home()


class NewConversationModal(ModalScreen):
    DEFAULT_CSS = MODAL_CSS.format(cls="NewConversationModal") + """
    NewConversationModal > Container {
        width: 90%;
        max-width: 150;
        height: 90%;
    }
    NewConversationModal #new-conv-columns {
        height: 1fr;
    }
    NewConversationModal #new-conv-left {
        width: 1fr;
        margin-right: 2;
    }
    NewConversationModal #new-conv-right {
        width: 1fr;
    }
    NewConversationModal #recent-dirs {
        height: 7;
        margin-bottom: 1;
    }
    NewConversationModal #dir-tree {
        height: 1fr;
        margin-bottom: 1;
    }
    NewConversationModal #resume-sessions {
        height: 8;
        margin-left: 4;
    }
    NewConversationModal #from-pr-input {
        margin-left: 4;
    }
    NewConversationModal .group-title {
        text-style: bold;
        color: green;
        margin-top: 1;
    }
    NewConversationModal Checkbox {
        border: none;
        padding: 0;
        height: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, storage: Storage, browse_root: Path | None = None):
        super().__init__()
        self.storage = storage
        self.browse_root = browse_root or default_browse_root()
        self.selection = DEFAULT_SELECTION
        self._sessions_for: str | None = None
        self._session_ids: list[str] = []

    def compose(self):
        right = []
        for group in GROUPS:
            if group.title:
                right.append(Static(group.title, classes="group-title"))
            for option in group.options:
                right.append(Checkbox(option.label, value=option.key in self.selection, id=f"opt-{option.key}"))
                if option.key == SESSION_RESUME:
                    right.append(OptionList(id="resume-sessions"))
                elif option.key == SESSION_FROM_PR:
                    right.append(Input(placeholder="PR number or URL", id="from-pr-input"))
        recent = [Option(escape(p), id=p) for p in self.storage.recent_project_paths()]
        box = Container(
            Horizontal(
                Vertical(
                    Static("Recent directories", classes="modal-label"),
                    OptionList(*recent, id="recent-dirs"),
                    Static("Browse", classes="modal-label"),
                    _DirectoriesOnly(str(self.browse_root), id="dir-tree"),
                    Static("Path", classes="modal-label"),
                    Input(placeholder="/path/to/project", id="launch-path"),
                    id="new-conv-left",
                ),
                VerticalScroll(*right, id="new-conv-right"),
                id="new-conv-columns",
            ),
            Static("Name (optional)", classes="modal-label"),
            Input(placeholder="defaults to the directory name", id="launch-name"),
            Static("", id="launch-error", classes="modal-error"),
            Horizontal(
                Button("Start", id="launch-start", classes="modal-submit"),
                Button("Cancel", id="launch-cancel", classes="modal-cancel"),
                classes="modal-buttons",
            ),
        )
        box.border_title = "New conversation"
        yield box

    def on_mount(self) -> None:
        self._sync_session_widgets()

    # --- directory ------------------------------------------------------

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "recent-dirs":
            self.query_one("#launch-path", Input).value = event.option.id

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.query_one("#launch-path", Input).value = str(event.path)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "launch-path":
            self._sync_session_widgets()

    def _path(self) -> str:
        return str(Path(self.query_one("#launch-path", Input).value.strip()).expanduser())

    # --- attributes -----------------------------------------------------

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        key = event.checkbox.id.removeprefix("opt-")
        if event.value == (key in self.selection):
            return  # echo of our own sync below
        self.selection = toggle(self.selection, key, event.value)
        for checkbox in self.query(Checkbox):
            wanted = checkbox.id.removeprefix("opt-") in self.selection
            if checkbox.value != wanted:
                checkbox.value = wanted
        self._sync_session_widgets()

    def _sync_session_widgets(self) -> None:
        mode = session_mode(self.selection)
        self.query_one(f"#opt-{FORK}", Checkbox).disabled = mode == SESSION_NEW
        self.query_one("#from-pr-input", Input).display = mode == SESSION_FROM_PR
        sessions = self.query_one("#resume-sessions", OptionList)
        sessions.display = mode == SESSION_RESUME
        path = self._path() if self.query_one("#launch-path", Input).value.strip() else ""
        if mode == SESSION_RESUME and path != self._sessions_for:
            self._sessions_for = path
            sessions.clear_options()
            found = list_sessions_for_directory(path) if path and Path(path).is_dir() else []
            self._session_ids = [s.session_id for s in found]
            sessions.add_options([
                Option(f"{s.modified:%Y-%m-%d %H:%M} · {s.message_count} msgs · {escape(s.first_prompt)}")
                for s in found
            ])
            if found:
                sessions.highlighted = 0

    # --- buttons --------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "launch-cancel":
            self.dismiss(None)
            return
        if event.button.id != "launch-start":
            return
        error = self.query_one("#launch-error", Static)
        if not self.query_one("#launch-path", Input).value.strip():
            error.update("Choose a directory.")
            return
        session_id = None
        if session_mode(self.selection) == SESSION_RESUME:
            highlighted = self.query_one("#resume-sessions", OptionList).highlighted
            if highlighted is not None and highlighted < len(self._session_ids):
                session_id = self._session_ids[highlighted]
        try:
            queue = start_conversation(
                self.storage,
                self._path(),
                self.selection,
                name=self.query_one("#launch-name", Input).value,
                session_id=session_id,
                pr=self.query_one("#from-pr-input", Input).value,
            )
        except ValueError as exc:
            error.update(escape(str(exc)))
            return
        self.dismiss(queue.id)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: New conversation dialog (directory picker + launch attributes)`

---

### Task 7: Conversations — chat input, status, queued messages, `n` everywhere

**Files:**
- Modify: `src/cc_continue/tui/layout.py`, `src/cc_continue/tui/conversations.py`, `src/cc_continue/tui/queue_detail.py`
- Test: `tests/test_tui_conversations.py` (append + adjust button-label test), `tests/test_tui_layout.py` (append)

**Interfaces:**
- Consumes: Tasks 1, 2, 6.
- Produces: `NEW_CONVERSATION_BUTTON` in layout; `SidebarScreen.action_new_conversation()`, `SidebarScreen.open_conversation(queue_id)`; `ConversationsScreen(storage, select_queue_id: int | None = None)`; ids `#conversation-header`, `#conversation-status`, `#message-input`; queued bubbles have class `message-box-queued`.

- [ ] **Step 1: Failing tests** (append to `tests/test_tui_conversations.py`)

```python
from textual.widgets import Input


async def _open(storage, **kw):
    screen = ConversationsScreen(storage, **kw)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    return _HostApp()


@pytest.mark.asyncio
async def test_message_input_queues_prompt_and_shows_queued_bubble(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    storage = Storage(tmp_path / "history.db")
    q = storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa", launch_flags=["--model", "haiku"])
    app = await _open(storage)
    async with app.run_test() as pilot:
        await pilot.pause()
        box = app.screen.query_one("#message-input", Input)
        box.focus()
        await pilot.press(*"ahoj")
        await pilot.press("enter")
        await pilot.pause()
        assert [i.prompt_text for i in storage.list_pending_items(q.id)] == ["ahoj"]
        assert box.value == ""
        queued = app.screen.query(".message-box-queued")
        assert len(queued) == 1 and "ahoj" in str(queued.first().render())
        assert "1 queued" in str(app.screen.query_one("#conversation-status").render())
        assert "Haiku" in str(app.screen.query_one("#conversation-header").render())


@pytest.mark.asyncio
async def test_new_queue_appears_and_select_queue_id_opens_it(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    storage = Storage(tmp_path / "history.db")
    storage.create_queue("a", "/tmp/a", "s-a")
    b = storage.create_queue("b", "/tmp/b", "s-b")
    app = await _open(storage, select_queue_id=b.id)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen._current_queue_id == b.id
        storage.create_queue("c", "/tmp/c", "s-c")
        await app.screen._refresh_current()
        await pilot.pause()
        table = app.screen.query_one("#conversation-queue-list", DataTable)
        assert table.row_count == 3
        assert app.screen._current_queue_id == b.id


@pytest.mark.asyncio
async def test_status_line_shows_waiting_for_reset(tmp_path, monkeypatch):
    from datetime import datetime
    from cc_continue.models import QueueStatus
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    storage = Storage(tmp_path / "history.db")
    q = storage.create_queue("a", "/tmp/a", "s-a")
    storage.update_queue_status(q.id, QueueStatus.WAITING_RETRY, next_retry_at=datetime(2026, 10, 12, 15, 0))
    app = await _open(storage)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "15:00" in str(app.screen.query_one("#conversation-status").render())
```

Append to `tests/test_tui_layout.py`:

```python
@pytest.mark.asyncio
async def test_n_opens_new_conversation_and_lands_in_conversations(tmp_path):
    from cc_continue.tui.new_conversation import NewConversationModal
    app = _app(tmp_path)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, NewConversationModal)
        app.screen.query_one("#launch-path").value = str(tmp_path)
        await pilot.click("#launch-start")
        await pilot.pause()
        assert isinstance(app.screen, ConversationsScreen)
        newest = max(q.id for q in app.screen.storage.list_queues())
        assert app.screen._current_queue_id == newest
```

Adjust the existing button-label test in `tests/test_tui_conversations.py` to expect `"New conversation (n)"` instead of `"Add prompt (a)"`.

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**

`layout.py`:
  - `NEW_CONVERSATION_BUTTON = SidebarButton("sidebar-new-conversation", "New conversation (n)", "green", "new_conversation")`
  - Base `BINDINGS` add `("n", "new_conversation", "New conversation")`.
  - `_make_view(view, **kwargs)` passes kwargs to the screen constructor (only `ConversationsScreen` takes `select_queue_id`); split `action_goto` into `action_goto(view)` → `self._navigate(view, self._make_view(view))` and `_navigate(view, screen)` holding the current stack logic.
  - Methods:

```python
    def action_new_conversation(self) -> None:
        from cc_continue.tui.new_conversation import NewConversationModal

        def opened(queue_id: int | None) -> None:
            if queue_id is not None:
                self.open_conversation(queue_id)

        self.app.push_screen(NewConversationModal(self.storage), opened)

    def open_conversation(self, queue_id: int) -> None:
        self._navigate("conversations", self._make_view("conversations", select_queue_id=queue_id))
```

`conversations.py`:
  - `__init__(self, storage, select_queue_id=None)`; keep `self._queue_ids: list[int]`, `self._rendered_key` (tuple of event count + pending ids) to avoid needless re-renders.
  - `sidebar_buttons` → `[NEW_CONVERSATION_BUTTON, LIVE_SESSIONS_BUTTON, RETRY_BUTTON]`.
  - `compose_main` yields `Static(id="conversation-header")`, `VerticalScroll(id="conversation-transcript")`, `Static(id="conversation-status")`, `Input(placeholder="Message Claude… (Enter to send, Esc back)", id="message-input")`.
  - `_rebuild_queue_list()` fills the table from `storage.list_queues()`, records `_queue_ids`, moves the cursor to the current queue.
  - Row highlight uses `self._queue_ids[event.cursor_row]`.
  - `_render_transcript` also mounts one `Static(f"[b]You[/b]  [dim]queued[/dim]\n{escape(text)}", classes="message-box message-box-queued")` per pending item after the transcript events, then scrolls to end; updates header + status.
  - `_refresh_current` (2s): rebuild list when queue ids changed, re-parse new transcript lines, re-render when events or pending ids changed, always update the status line. A queue whose transcript didn't exist yet (`path is None`) is re-looked-up each tick (new conversations get their JSONL only after the first run starts).
  - `on_input_submitted` for `#message-input`: strip, ignore empty, `storage.add_queue_item(current, text)`, clear the input, re-render.
  - `open_conversation(queue_id)` override: select in place (rebuild list, `_show_queue`).
  - Status line text:

```python
    def _status_text(self, queue, pending: int) -> str:
        if queue.status == QueueStatus.RUNNING:
            text = "[bold green]● Claude is working…[/]"
        elif queue.status == QueueStatus.WAITING_RETRY and queue.next_retry_at:
            text = f"[bold yellow]⏸ Waiting for usage limit reset until {queue.next_retry_at:%H:%M}[/]"
        elif queue.status == QueueStatus.BLOCKED_ERROR:
            text = f"[bold red]✖ Blocked: {escape((queue.last_error or '')[:120])} — press r to retry[/]"
        else:
            text = "[dim]Ready[/dim]"
        return f"{text}  ·  {pending} queued" if pending else text
```

  - Header: `f"[b]{escape(queue.name)}[/b]  [dim]{escape(queue.project_path)}[/dim]  ·  {escape(describe_flags(queue.launch_flags))}"` plus `"  ·  [yellow]first run: …[/]"` listing `first_run_flags` when set.
  - CSS: `#conversation-header` height auto, padding 0 1, margin-bottom 1; `#conversation-status` height 1; `.message-box-queued { border: round $panel-lighten-2; color: $text-muted; }`.

`queue_detail.py`: info lines get `f"Launch: {escape(describe_flags(queue.launch_flags))}"`.

- [ ] **Step 4: Run** full suite → PASS.
- [ ] **Step 5: Commit** `feat: chat with conversations in the TUI; n starts a new one from anywhere`

---

### Task 8: Docs, screenshots, live verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** README — new section "Starting a new conversation" (dialog, attribute table, headless caveat: no interactive approvals/slash commands, permission chosen up front; resume/continue/fork/from-PR semantics), update key list (`n`).
- [ ] **Step 2:** Render screenshots: `.venv/bin/python ~/Documents/CC/bin/cc-continue-tui-screenshots.py <scratch>/launcher --only conversations` plus the new modal (add `new_conversation` to the script's screen list) and inspect them.
- [ ] **Step 3:** Live check: `systemctl --user restart cc-continue cc-continue-tui`; in a scratch directory start a conversation with Haiku via the dialog, send "Řekni jen OK", see the reply appear in Conversations; then start a fork of it and check the queue adopted a new session id.
- [ ] **Step 4:** Full suite green; commit `docs: document starting conversations from the TUI`.
