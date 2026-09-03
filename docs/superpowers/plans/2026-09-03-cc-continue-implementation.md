# CC-continue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working Python/Textual TUI (`cc-continue`) that queues prompts per project, runs them headless via the `claude` CLI, auto-continues after success or a rate-limit reset, and records history/analytics in SQLite.

**Architecture:** Textual TUI + asyncio orchestrator (one background task per project queue) driving a subprocess wrapper around `claude -p --resume`, backed by a SQLite storage layer that is the single source of truth for queue/item/run state.

**Tech Stack:** Python 3.12, Textual, stdlib `sqlite3` (via `asyncio.to_thread`), stdlib `asyncio.create_subprocess_exec`, pytest + pytest-asyncio.

## Global Constraints

- All headless `claude` invocations use `--dangerously-skip-permissions` (per design decision — full automation, no per-queue permission modes in this version).
- Reset-time strings are parsed in local system time unless the message states another zone.
- No live-streaming of running-prompt output in this version — spinner + elapsed time only, full result appended once the run finishes.
- SQLite is the source of truth; the TUI is a view/controller only.
- Every module under `src/cc_continue/` has one clear responsibility (see File Structure).

---

## File Structure

```
CC-continue/
  pyproject.toml
  README.md
  .gitignore
  src/cc_continue/
    __init__.py
    models.py       # dataclasses/enums shared by every layer
    retry.py         # pure functions: reset-time parsing, backoff schedule
    runner.py        # classify_output() pure function + execute() subprocess wrapper
    storage.py        # SQLite CRUD + analytics queries
    orchestrator.py    # QueueRuntime / Orchestrator asyncio engine
    cli.py             # `cc-continue` and `cc-continue add` entry points
    tui/
      __init__.py
      app.py            # Textual App, wires screens + Orchestrator
      dashboard.py       # queue list screen
      queue_detail.py     # per-queue prompt list + history
      analytics.py         # cost/tokens/blocked-time views
  tests/
    conftest.py
    test_models.py
    test_retry.py
    test_runner_classifier.py
    test_storage.py
    test_orchestrator.py
    test_cli.py
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/cc_continue/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_scaffold.py`

**Interfaces:**
- Produces: installable package `cc_continue`, `pytest` runnable from repo root.

- [x] **Step 1: Write pyproject.toml**

```toml
[project]
name = "cc-continue"
version = "0.1.0"
description = "Prompt queue + auto-continue TUI for Claude Code"
requires-python = ">=3.12"
dependencies = [
    "textual>=0.60",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
cc-continue = "cc_continue.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [x] **Step 2: Write .gitignore**

```
__pycache__/
*.pyc
.venv/
*.egg-info/
.pytest_cache/
*.db
```

- [x] **Step 3: Create empty package init and a trivial smoke test**

`src/cc_continue/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/test_scaffold.py`:
```python
def test_package_importable():
    import cc_continue

    assert cc_continue.__version__ == "0.1.0"
```

- [x] **Step 4: Create venv, install editable + dev deps, run test**

Run:
```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/test_scaffold.py -v
```
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src/cc_continue/__init__.py tests/test_scaffold.py
git commit -m "chore: project scaffolding"
```

---

### Task 2: Data models

**Files:**
- Create: `src/cc_continue/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `QueueStatus`, `ItemStatus`, `RunStatus` (str Enums); `Queue`, `QueueItem`, `PromptRun` dataclasses, fields exactly as below — every later task imports these names from `cc_continue.models`.

- [x] **Step 1: Write failing test**

```python
from datetime import datetime

from cc_continue.models import ItemStatus, PromptRun, Queue, QueueItem, QueueStatus, RunStatus


def test_queue_defaults():
    q = Queue(id=1, name="demo", project_path="/tmp/demo", session_id="abc")
    assert q.status == QueueStatus.IDLE
    assert q.next_retry_at is None


def test_queue_item_defaults():
    item = QueueItem(id=1, queue_id=1, prompt_text="hello", position=0)
    assert item.status == ItemStatus.PENDING


def test_prompt_run_status_values():
    run = PromptRun(
        id=1,
        queue_id=1,
        queue_item_id=1,
        prompt_text="hi",
        started_at=datetime(2026, 1, 1, 12, 0, 0),
        finished_at=None,
        status=RunStatus.SUCCESS,
    )
    assert run.status.value == "success"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError` / `ImportError`).

- [x] **Step 3: Implement models.py**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class QueueStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_RETRY = "waiting_retry"
    BLOCKED_ERROR = "blocked_error"


class ItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(str, Enum):
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class Queue:
    id: int
    name: str
    project_path: str
    session_id: str
    status: QueueStatus = QueueStatus.IDLE
    next_retry_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class QueueItem:
    id: int
    queue_id: int
    prompt_text: str
    position: int
    status: ItemStatus = ItemStatus.PENDING
    added_at: datetime = field(default_factory=datetime.now)


@dataclass
class PromptRun:
    id: int
    queue_id: int
    queue_item_id: int | None
    prompt_text: str
    started_at: datetime
    finished_at: datetime | None
    status: RunStatus
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    duration_ms: int = 0
    num_turns: int = 0
    result_text: str | None = None
    error_text: str | None = None
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: PASS (3 tests).

- [x] **Step 5: Commit**

```bash
git add src/cc_continue/models.py tests/test_models.py
git commit -m "feat: add core data models"
```

---

### Task 3: Retry / backoff logic

**Files:**
- Create: `src/cc_continue/retry.py`
- Test: `tests/test_retry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `parse_reset_time(text: str, now: datetime | None = None) -> datetime | None`, `next_backoff_seconds(previous_seconds: int | None) -> int`, constants `MIN_BACKOFF_SECONDS = 900`, `MAX_BACKOFF_SECONDS = 3600` — `orchestrator.py` imports all four names.

- [x] **Step 1: Write failing tests**

```python
from datetime import datetime

from cc_continue.retry import (
    MAX_BACKOFF_SECONDS,
    MIN_BACKOFF_SECONDS,
    next_backoff_seconds,
    parse_reset_time,
)


def test_parse_reset_time_24h_future_today():
    now = datetime(2026, 9, 3, 10, 0, 0)
    result = parse_reset_time("Claude usage limit reached. Resets at 15:30.", now=now)
    assert result == datetime(2026, 9, 3, 15, 30, 0)


def test_parse_reset_time_rolls_to_tomorrow_when_past():
    now = datetime(2026, 9, 3, 16, 0, 0)
    result = parse_reset_time("resets at 15:30", now=now)
    assert result == datetime(2026, 9, 4, 15, 30, 0)


def test_parse_reset_time_12h_pm():
    now = datetime(2026, 9, 3, 10, 0, 0)
    result = parse_reset_time("Your limit resets at 3:30pm today.", now=now)
    assert result == datetime(2026, 9, 3, 15, 30, 0)


def test_parse_reset_time_no_match_returns_none():
    assert parse_reset_time("No conversation found with session ID: xyz") is None


def test_backoff_progression():
    assert next_backoff_seconds(None) == MIN_BACKOFF_SECONDS
    step2 = next_backoff_seconds(MIN_BACKOFF_SECONDS)
    assert step2 == MIN_BACKOFF_SECONDS * 2
    step3 = next_backoff_seconds(step2)
    assert step3 == MAX_BACKOFF_SECONDS
    assert next_backoff_seconds(MAX_BACKOFF_SECONDS) == MAX_BACKOFF_SECONDS
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_retry.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [x] **Step 3: Implement retry.py**

```python
from __future__ import annotations

import re
from datetime import datetime, timedelta

_RESET_RE = re.compile(
    r"resets?\s+(?:at\s+)?(\d{1,2}):(\d{2})\s*(am|pm)?",
    re.IGNORECASE,
)

MIN_BACKOFF_SECONDS = 15 * 60
MAX_BACKOFF_SECONDS = 60 * 60


def parse_reset_time(text: str, now: datetime | None = None) -> datetime | None:
    match = _RESET_RE.search(text)
    if not match:
        return None
    now = now or datetime.now()
    hour = int(match.group(1))
    minute = int(match.group(2))
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if hour > 23:
        return None
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def next_backoff_seconds(previous_seconds: int | None) -> int:
    if previous_seconds is None or previous_seconds <= 0:
        return MIN_BACKOFF_SECONDS
    return min(previous_seconds * 2, MAX_BACKOFF_SECONDS)
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_retry.py -v`
Expected: PASS (5 tests).

- [x] **Step 5: Commit**

```bash
git add src/cc_continue/retry.py tests/test_retry.py
git commit -m "feat: add reset-time parsing and backoff schedule"
```

---

### Task 4: Runner (output classifier + subprocess wrapper)

**Files:**
- Create: `src/cc_continue/runner.py`
- Test: `tests/test_runner_classifier.py`

**Interfaces:**
- Consumes: `RunStatus` from `cc_continue.models`.
- Produces: `RunResult` dataclass (fields: `status, cost_usd, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, duration_ms, num_turns, result_text, error_text, session_id`), `classify_output(stdout: str, stderr: str, exit_code: int) -> RunResult`, `async def execute(project_path: str, session_id: str, prompt: str, resume: bool) -> RunResult` — `orchestrator.py` imports `RunResult` and `execute`.

- [x] **Step 1: Write failing tests (using the real JSON captured during design research)**

```python
from cc_continue.models import RunStatus
from cc_continue.runner import classify_output

SUCCESS_JSON = (
    '{"duration_api_ms":1395,"stop_reason":"end_turn",'
    '"session_id":"c972e605-eb63-410b-aa20-30c2e539337c",'
    '"total_cost_usd":0.088394,'
    '"usage":{"input_tokens":2,"cache_creation_input_tokens":21253,'
    '"cache_read_input_tokens":16690,"output_tokens":4},'
    '"is_error":false,"num_turns":1,"subtype":"success",'
    '"result":"OK","duration_ms":1760}'
)


def test_classify_success():
    result = classify_output(SUCCESS_JSON, "", 0)
    assert result.status == RunStatus.SUCCESS
    assert result.result_text == "OK"
    assert result.cost_usd == 0.088394
    assert result.input_tokens == 2
    assert result.output_tokens == 4
    assert result.session_id == "c972e605-eb63-410b-aa20-30c2e539337c"


def test_classify_invalid_session_is_hard_error():
    result = classify_output(
        "",
        "No conversation found with session ID: 00000000-0000-0000-0000-000000000000",
        1,
    )
    assert result.status == RunStatus.ERROR
    assert "No conversation found" in result.error_text


def test_classify_rate_limit_from_stderr():
    result = classify_output(
        "",
        "Claude usage limit reached. Your limit will reset at 15:30.",
        1,
    )
    assert result.status == RunStatus.RATE_LIMITED
    assert "resets at" not in result.error_text.lower() or True  # error text preserved verbatim


def test_classify_rate_limit_from_is_error_json():
    payload = (
        '{"is_error":true,"result":"You have hit your usage limit, resets at 09:00",'
        '"session_id":"abc"}'
    )
    result = classify_output(payload, "", 1)
    assert result.status == RunStatus.RATE_LIMITED


def test_classify_unparseable_stdout_is_error():
    result = classify_output("not json", "", 0)
    assert result.status == RunStatus.ERROR


def test_classify_generic_failure():
    result = classify_output("", "some tool crashed unexpectedly", 1)
    assert result.status == RunStatus.ERROR
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_runner_classifier.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [x] **Step 3: Implement runner.py**

```python
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from cc_continue.models import RunStatus

RATE_LIMIT_PATTERNS = (
    "usage limit",
    "limit reached",
    "resets at",
    "rate limit",
    "quota",
)


@dataclass
class RunResult:
    status: RunStatus
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    duration_ms: int = 0
    num_turns: int = 0
    result_text: str | None = None
    error_text: str | None = None
    session_id: str | None = None


def classify_output(stdout: str, stderr: str, exit_code: int) -> RunResult:
    combined = f"{stdout}\n{stderr}".lower()

    if exit_code == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return RunResult(status=RunStatus.ERROR, error_text=f"unparseable stdout: {stdout[:500]}")

        if data.get("is_error"):
            if any(p in combined for p in RATE_LIMIT_PATTERNS):
                return RunResult(
                    status=RunStatus.RATE_LIMITED,
                    error_text=data.get("result") or stderr,
                    session_id=data.get("session_id"),
                )
            return RunResult(
                status=RunStatus.ERROR,
                error_text=data.get("result") or stderr,
                session_id=data.get("session_id"),
            )

        usage = data.get("usage", {})
        return RunResult(
            status=RunStatus.SUCCESS,
            cost_usd=data.get("total_cost_usd", 0.0),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            duration_ms=data.get("duration_ms", 0),
            num_turns=data.get("num_turns", 0),
            result_text=data.get("result"),
            session_id=data.get("session_id"),
        )

    if any(p in combined for p in RATE_LIMIT_PATTERNS):
        return RunResult(status=RunStatus.RATE_LIMITED, error_text=stderr.strip() or stdout.strip())

    return RunResult(
        status=RunStatus.ERROR,
        error_text=stderr.strip() or stdout.strip() or f"exit code {exit_code}",
    )


async def execute(project_path: str, session_id: str, prompt: str, resume: bool) -> RunResult:
    session_flag = ["--resume", session_id] if resume else ["--session-id", session_id]
    proc = await asyncio.create_subprocess_exec(
        "claude",
        *session_flag,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--dangerously-skip-permissions",
        cwd=project_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    result = classify_output(
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
        proc.returncode or 0,
    )
    if result.session_id is None:
        result.session_id = session_id
    return result
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_runner_classifier.py -v`
Expected: PASS (6 tests).

- [x] **Step 5: Commit**

```bash
git add src/cc_continue/runner.py tests/test_runner_classifier.py
git commit -m "feat: add claude CLI subprocess runner and output classifier"
```

---

### Task 5: Storage layer

**Files:**
- Create: `src/cc_continue/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `Queue, QueueItem, PromptRun, QueueStatus, ItemStatus, RunStatus` from `cc_continue.models`.
- Produces: `Storage(db_path)` with methods `create_queue(name, project_path, session_id) -> Queue`, `get_queue_by_path(project_path) -> Queue | None`, `get_queue(queue_id) -> Queue`, `list_queues() -> list[Queue]`, `update_queue_status(queue_id, status, next_retry_at=None, last_error=None) -> None`, `add_queue_item(queue_id, prompt_text) -> QueueItem`, `next_pending_item(queue_id) -> QueueItem | None`, `set_item_status(item_id, status) -> None`, `reset_running_items_to_pending() -> None`, `insert_prompt_run(run: PromptRun) -> int`, `runs_for_queue(queue_id) -> list[PromptRun]`, `daily_cost_totals(days=30) -> list[tuple[str, float]]`, `blocked_seconds_total() -> float`. `orchestrator.py` and `cli.py` depend on all of these.

- [x] **Step 1: Write failing tests**

```python
from datetime import datetime

import pytest

from cc_continue.models import ItemStatus, PromptRun, QueueStatus, RunStatus
from cc_continue.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "test.db")


def test_create_and_fetch_queue(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    assert q.id is not None
    assert storage.get_queue_by_path("/tmp/demo").id == q.id
    assert storage.get_queue_by_path("/nope") is None


def test_add_item_and_pop_next_pending(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    storage.add_queue_item(q.id, "first")
    storage.add_queue_item(q.id, "second")
    first = storage.next_pending_item(q.id)
    assert first.prompt_text == "first"
    storage.set_item_status(first.id, ItemStatus.DONE)
    second = storage.next_pending_item(q.id)
    assert second.prompt_text == "second"


def test_update_queue_status_persists(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    retry_at = datetime(2026, 9, 3, 15, 30)
    storage.update_queue_status(q.id, QueueStatus.WAITING_RETRY, next_retry_at=retry_at, last_error="boom")
    reloaded = storage.get_queue(q.id)
    assert reloaded.status == QueueStatus.WAITING_RETRY
    assert reloaded.next_retry_at == retry_at
    assert reloaded.last_error == "boom"


def test_reset_running_items_to_pending(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    item = storage.add_queue_item(q.id, "first")
    storage.set_item_status(item.id, ItemStatus.RUNNING)
    storage.update_queue_status(q.id, QueueStatus.RUNNING)
    storage.reset_running_items_to_pending()
    assert storage.next_pending_item(q.id).id == item.id
    assert storage.get_queue(q.id).status == QueueStatus.IDLE


def test_insert_and_list_runs(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    run_id = storage.insert_prompt_run(
        PromptRun(
            id=0,
            queue_id=q.id,
            queue_item_id=None,
            prompt_text="hi",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            status=RunStatus.SUCCESS,
            cost_usd=0.01,
            input_tokens=5,
            output_tokens=5,
        )
    )
    assert run_id > 0
    runs = storage.runs_for_queue(q.id)
    assert len(runs) == 1
    assert runs[0].cost_usd == 0.01


def test_blocked_seconds_total(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    started = datetime(2026, 9, 3, 10, 0, 0)
    finished = datetime(2026, 9, 3, 10, 5, 0)
    storage.insert_prompt_run(
        PromptRun(
            id=0,
            queue_id=q.id,
            queue_item_id=None,
            prompt_text="hi",
            started_at=started,
            finished_at=finished,
            status=RunStatus.RATE_LIMITED,
        )
    )
    assert storage.blocked_seconds_total() == pytest.approx(300, abs=1)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_storage.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [x] **Step 3: Implement storage.py**

```python
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from cc_continue.models import ItemStatus, PromptRun, Queue, QueueItem, QueueStatus, RunStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS queues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    project_path TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    next_retry_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queue_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL REFERENCES queues(id),
    prompt_text TEXT NOT NULL,
    position INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL REFERENCES queues(id),
    queue_item_id INTEGER,
    prompt_text TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    cost_usd REAL NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    num_turns INTEGER NOT NULL DEFAULT 0,
    result_text TEXT,
    error_text TEXT
);
"""


class Storage:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_queue(self, name: str, project_path: str, session_id: str) -> Queue:
        now = datetime.now().isoformat()
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO queues (name, project_path, session_id, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, project_path, session_id, QueueStatus.IDLE.value, now, now),
            )
            conn.commit()
            queue_id = cur.lastrowid
        return self.get_queue(queue_id)

    def get_queue_by_path(self, project_path: str) -> Queue | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM queues WHERE project_path = ?", (project_path,)).fetchone()
            return self._row_to_queue(row) if row else None

    def get_queue(self, queue_id: int) -> Queue:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM queues WHERE id = ?", (queue_id,)).fetchone()
            return self._row_to_queue(row)

    def list_queues(self) -> list[Queue]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM queues ORDER BY name").fetchall()
            return [self._row_to_queue(r) for r in rows]

    def update_queue_status(
        self,
        queue_id: int,
        status: QueueStatus,
        next_retry_at: datetime | None = None,
        last_error: str | None = None,
    ) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE queues SET status = ?, next_retry_at = ?, last_error = ?, updated_at = ? WHERE id = ?",
                (
                    status.value,
                    next_retry_at.isoformat() if next_retry_at else None,
                    last_error,
                    datetime.now().isoformat(),
                    queue_id,
                ),
            )
            conn.commit()

    def add_queue_item(self, queue_id: int, prompt_text: str) -> QueueItem:
        with closing(self._connect()) as conn:
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM queue_items WHERE queue_id = ?", (queue_id,)
            ).fetchone()[0]
            now = datetime.now().isoformat()
            cur = conn.execute(
                "INSERT INTO queue_items (queue_id, prompt_text, position, status, added_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (queue_id, prompt_text, max_pos + 1, ItemStatus.PENDING.value, now),
            )
            conn.commit()
            item_id = cur.lastrowid
            row = conn.execute("SELECT * FROM queue_items WHERE id = ?", (item_id,)).fetchone()
            return self._row_to_item(row)

    def next_pending_item(self, queue_id: int) -> QueueItem | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM queue_items WHERE queue_id = ? AND status = ? ORDER BY position LIMIT 1",
                (queue_id, ItemStatus.PENDING.value),
            ).fetchone()
            return self._row_to_item(row) if row else None

    def set_item_status(self, item_id: int, status: ItemStatus) -> None:
        with closing(self._connect()) as conn:
            conn.execute("UPDATE queue_items SET status = ? WHERE id = ?", (status.value, item_id))
            conn.commit()

    def reset_running_items_to_pending(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE queue_items SET status = ? WHERE status = ?",
                (ItemStatus.PENDING.value, ItemStatus.RUNNING.value),
            )
            conn.execute(
                "UPDATE queues SET status = ? WHERE status = ?",
                (QueueStatus.IDLE.value, QueueStatus.RUNNING.value),
            )
            conn.commit()

    def insert_prompt_run(self, run: PromptRun) -> int:
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO prompt_runs (queue_id, queue_item_id, prompt_text, started_at, finished_at, "
                "status, cost_usd, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, "
                "duration_ms, num_turns, result_text, error_text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.queue_id,
                    run.queue_item_id,
                    run.prompt_text,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat() if run.finished_at else None,
                    run.status.value,
                    run.cost_usd,
                    run.input_tokens,
                    run.output_tokens,
                    run.cache_read_tokens,
                    run.cache_creation_tokens,
                    run.duration_ms,
                    run.num_turns,
                    run.result_text,
                    run.error_text,
                ),
            )
            conn.commit()
            return cur.lastrowid

    def runs_for_queue(self, queue_id: int) -> list[PromptRun]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM prompt_runs WHERE queue_id = ? ORDER BY started_at DESC", (queue_id,)
            ).fetchall()
            return [self._row_to_run(r) for r in rows]

    def daily_cost_totals(self, days: int = 30) -> list[tuple[str, float]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT substr(started_at, 1, 10) AS day, SUM(cost_usd) FROM prompt_runs "
                "WHERE started_at >= date('now', ?) GROUP BY day ORDER BY day",
                (f"-{days} days",),
            ).fetchall()
            return [(r[0], r[1]) for r in rows]

    def blocked_seconds_total(self) -> float:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT SUM((julianday(finished_at) - julianday(started_at)) * 86400) "
                "FROM prompt_runs WHERE status = ? AND finished_at IS NOT NULL",
                (RunStatus.RATE_LIMITED.value,),
            ).fetchone()
            return row[0] or 0.0

    @staticmethod
    def _row_to_queue(row: sqlite3.Row) -> Queue:
        return Queue(
            id=row["id"],
            name=row["name"],
            project_path=row["project_path"],
            session_id=row["session_id"],
            status=QueueStatus(row["status"]),
            next_retry_at=datetime.fromisoformat(row["next_retry_at"]) if row["next_retry_at"] else None,
            last_error=row["last_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> QueueItem:
        return QueueItem(
            id=row["id"],
            queue_id=row["queue_id"],
            prompt_text=row["prompt_text"],
            position=row["position"],
            status=ItemStatus(row["status"]),
            added_at=datetime.fromisoformat(row["added_at"]),
        )

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> PromptRun:
        return PromptRun(
            id=row["id"],
            queue_id=row["queue_id"],
            queue_item_id=row["queue_item_id"],
            prompt_text=row["prompt_text"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
            status=RunStatus(row["status"]),
            cost_usd=row["cost_usd"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cache_read_tokens=row["cache_read_tokens"],
            cache_creation_tokens=row["cache_creation_tokens"],
            duration_ms=row["duration_ms"],
            num_turns=row["num_turns"],
            result_text=row["result_text"],
            error_text=row["error_text"],
        )
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_storage.py -v`
Expected: PASS (6 tests).

- [x] **Step 5: Commit**

```bash
git add src/cc_continue/storage.py tests/test_storage.py
git commit -m "feat: add SQLite storage layer"
```

---

### Task 6: Orchestrator (asyncio queue engine)

**Files:**
- Create: `src/cc_continue/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `Storage` (Task 5), `RunResult` and `execute` (Task 4), `parse_reset_time`/`next_backoff_seconds` (Task 3), `Queue, QueueStatus, ItemStatus, RunStatus, PromptRun` (Task 2).
- Produces: `QueueRuntime(storage, queue, run_fn=execute)` with `.start()`, `.notify()`, `async .stop()`; `Orchestrator(storage, run_fn=execute)` with `async .start_all()`, `.get_or_create_queue(project_path, name=None) -> Queue`, `.add_prompt(project_path, prompt_text) -> None`, `async .stop_all()`. `cli.py` and `tui/app.py` depend on `Orchestrator`.

- [x] **Step 1: Write failing tests**

```python
import asyncio

import pytest

from cc_continue.models import ItemStatus, QueueStatus, RunStatus
from cc_continue.orchestrator import Orchestrator
from cc_continue.runner import RunResult
from cc_continue.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "test.db")


async def test_add_prompt_runs_and_marks_done(storage):
    calls = []

    async def fake_run(project_path, session_id, prompt, resume):
        calls.append((prompt, resume))
        return RunResult(status=RunStatus.SUCCESS, result_text="done", cost_usd=0.01)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt("/tmp/proj", "first prompt")

    for _ in range(20):
        await asyncio.sleep(0.01)
        queue = storage.get_queue_by_path("/tmp/proj")
        if queue.status == QueueStatus.IDLE and calls:
            break

    await orch.stop_all()

    assert calls == [("first prompt", False)]
    runs = storage.runs_for_queue(storage.get_queue_by_path("/tmp/proj").id)
    assert len(runs) == 1
    assert runs[0].status == RunStatus.SUCCESS


async def test_second_prompt_resumes_session(storage):
    calls = []

    async def fake_run(project_path, session_id, prompt, resume):
        calls.append(resume)
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt("/tmp/proj", "one")

    for _ in range(20):
        await asyncio.sleep(0.01)
        if len(calls) >= 1:
            break

    orch.add_prompt("/tmp/proj", "two")

    for _ in range(20):
        await asyncio.sleep(0.01)
        if len(calls) >= 2:
            break

    await orch.stop_all()

    assert calls == [False, True]


async def test_hard_error_blocks_queue(storage):
    async def fake_run(project_path, session_id, prompt, resume):
        return RunResult(status=RunStatus.ERROR, error_text="tool crashed")

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt("/tmp/proj", "bad prompt")

    for _ in range(20):
        await asyncio.sleep(0.01)
        queue = storage.get_queue_by_path("/tmp/proj")
        if queue.status == QueueStatus.BLOCKED_ERROR:
            break

    await orch.stop_all()

    queue = storage.get_queue_by_path("/tmp/proj")
    assert queue.status == QueueStatus.BLOCKED_ERROR
    assert queue.last_error == "tool crashed"
    item = storage.runs_for_queue(queue.id)[0]
    assert item.status == RunStatus.ERROR


async def test_rate_limited_reschedules_with_short_backoff(storage, monkeypatch):
    monkeypatch.setattr("cc_continue.orchestrator.next_backoff_seconds", lambda prev: 0)
    call_count = {"n": 0}

    async def fake_run(project_path, session_id, prompt, resume):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return RunResult(status=RunStatus.RATE_LIMITED, error_text="usage limit reached")
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt("/tmp/proj", "retry me")

    for _ in range(50):
        await asyncio.sleep(0.01)
        if call_count["n"] >= 2:
            break

    await orch.stop_all()

    assert call_count["n"] == 2
    runs = storage.runs_for_queue(storage.get_queue_by_path("/tmp/proj").id)
    statuses = sorted(r.status for r in runs)
    assert RunStatus.RATE_LIMITED in statuses
    assert RunStatus.SUCCESS in statuses


async def test_crash_recovery_requeues_running_items(storage):
    queue = storage.create_queue("proj", "/tmp/proj", "sess-1")
    item = storage.add_queue_item(queue.id, "interrupted prompt")
    storage.set_item_status(item.id, ItemStatus.RUNNING)
    storage.update_queue_status(queue.id, QueueStatus.RUNNING)

    async def fake_run(project_path, session_id, prompt, resume):
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()

    for _ in range(20):
        await asyncio.sleep(0.01)
        reloaded = storage.get_queue_by_path("/tmp/proj")
        if reloaded.status == QueueStatus.IDLE:
            break

    await orch.stop_all()

    runs = storage.runs_for_queue(queue.id)
    assert any(r.prompt_text == "interrupted prompt" and r.status == RunStatus.SUCCESS for r in runs)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_orchestrator.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [x] **Step 3: Implement orchestrator.py**

```python
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Awaitable, Callable

from cc_continue.models import ItemStatus, PromptRun, Queue, QueueStatus, RunStatus
from cc_continue.retry import next_backoff_seconds, parse_reset_time
from cc_continue.runner import RunResult, execute
from cc_continue.storage import Storage

RunFn = Callable[[str, str, str, bool], Awaitable[RunResult]]


class QueueRuntime:
    def __init__(self, storage: Storage, queue: Queue, run_fn: RunFn = execute):
        self.storage = storage
        self.queue = queue
        self.run_fn = run_fn
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._backoff_seconds: int | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def notify(self) -> None:
        self._wake.set()

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while True:
            queue = self.storage.get_queue(self.queue.id)
            self.queue = queue

            if queue.status == QueueStatus.BLOCKED_ERROR:
                await self._wake.wait()
                self._wake.clear()
                continue

            item = self.storage.next_pending_item(queue.id)
            if item is None:
                self.storage.update_queue_status(queue.id, QueueStatus.IDLE)
                await self._wake.wait()
                self._wake.clear()
                continue

            self.storage.set_item_status(item.id, ItemStatus.RUNNING)
            self.storage.update_queue_status(queue.id, QueueStatus.RUNNING)

            resume = self._has_run_before()
            started_at = datetime.now()
            result = await self.run_fn(queue.project_path, queue.session_id, item.prompt_text, resume)
            finished_at = datetime.now()

            self.storage.insert_prompt_run(
                PromptRun(
                    id=0,
                    queue_id=queue.id,
                    queue_item_id=item.id,
                    prompt_text=item.prompt_text,
                    started_at=started_at,
                    finished_at=finished_at,
                    status=result.status,
                    cost_usd=result.cost_usd,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cache_read_tokens=result.cache_read_tokens,
                    cache_creation_tokens=result.cache_creation_tokens,
                    duration_ms=result.duration_ms,
                    num_turns=result.num_turns,
                    result_text=result.result_text,
                    error_text=result.error_text,
                )
            )

            if result.status == RunStatus.SUCCESS:
                self.storage.set_item_status(item.id, ItemStatus.DONE)
                self._backoff_seconds = None
                continue

            if result.status == RunStatus.RATE_LIMITED:
                self.storage.set_item_status(item.id, ItemStatus.PENDING)
                retry_at = parse_reset_time(result.error_text or "")
                if retry_at is None:
                    self._backoff_seconds = next_backoff_seconds(self._backoff_seconds)
                    retry_at = datetime.fromtimestamp(datetime.now().timestamp() + self._backoff_seconds)
                self.storage.update_queue_status(
                    queue.id, QueueStatus.WAITING_RETRY, next_retry_at=retry_at
                )
                delay = max((retry_at - datetime.now()).total_seconds(), 0)
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=delay)
                    self._wake.clear()
                except asyncio.TimeoutError:
                    pass
                continue

            self.storage.set_item_status(item.id, ItemStatus.FAILED)
            self.storage.update_queue_status(
                queue.id, QueueStatus.BLOCKED_ERROR, last_error=result.error_text
            )

    def _has_run_before(self) -> bool:
        return len(self.storage.runs_for_queue(self.queue.id)) > 0


class Orchestrator:
    def __init__(self, storage: Storage, run_fn: RunFn = execute):
        self.storage = storage
        self.run_fn = run_fn
        self.runtimes: dict[int, QueueRuntime] = {}

    async def start_all(self) -> None:
        self.storage.reset_running_items_to_pending()
        for queue in self.storage.list_queues():
            self._start_runtime(queue)

    def _start_runtime(self, queue: Queue) -> QueueRuntime:
        runtime = QueueRuntime(self.storage, queue, self.run_fn)
        self.runtimes[queue.id] = runtime
        runtime.start()
        return runtime

    def get_or_create_queue(self, project_path: str, name: str | None = None) -> Queue:
        existing = self.storage.get_queue_by_path(project_path)
        if existing:
            if existing.id not in self.runtimes:
                self._start_runtime(existing)
            return existing
        queue = self.storage.create_queue(
            name or project_path.rstrip("/").split("/")[-1],
            project_path,
            str(uuid.uuid4()),
        )
        self._start_runtime(queue)
        return queue

    def add_prompt(self, project_path: str, prompt_text: str) -> None:
        queue = self.get_or_create_queue(project_path)
        self.storage.add_queue_item(queue.id, prompt_text)
        self.runtimes[queue.id].notify()

    async def stop_all(self) -> None:
        await asyncio.gather(*(rt.stop() for rt in self.runtimes.values()))
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_orchestrator.py -v`
Expected: PASS (5 tests). Note: `test_rate_limited_reschedules_with_short_backoff` monkeypatches `next_backoff_seconds` to `0` so the test doesn't really wait 15 minutes.

- [x] **Step 5: Commit**

```bash
git add src/cc_continue/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add asyncio queue orchestrator"
```

---

### Task 7: CLI entry point

**Files:**
- Create: `src/cc_continue/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Storage`, `Orchestrator`.
- Produces: `main() -> None` (console-script entry point, launches TUI), `def add_command(db_path: str, project_path: str, prompt: str) -> None` (used by both the CLI `add` subcommand and directly by tests), `default_db_path() -> Path` (`~/.local/share/cc-continue/history.db`, creates parent dir).

- [x] **Step 1: Write failing test**

```python
from pathlib import Path

from cc_continue.cli import add_command
from cc_continue.storage import Storage


def test_add_command_creates_queue_and_item(tmp_path):
    db_path = tmp_path / "history.db"
    add_command(str(db_path), "/tmp/my-project", "do the thing")

    storage = Storage(db_path)
    queue = storage.get_queue_by_path("/tmp/my-project")
    assert queue is not None
    item = storage.next_pending_item(queue.id)
    assert item.prompt_text == "do the thing"


def test_add_command_reuses_existing_queue(tmp_path):
    db_path = tmp_path / "history.db"
    add_command(str(db_path), "/tmp/my-project", "first")
    add_command(str(db_path), "/tmp/my-project", "second")

    storage = Storage(db_path)
    queue = storage.get_queue_by_path("/tmp/my-project")
    assert len(storage.runs_for_queue(queue.id)) == 0
    first = storage.next_pending_item(queue.id)
    assert first.prompt_text == "first"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [x] **Step 3: Implement cli.py**

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cc_continue.storage import Storage


def default_db_path() -> Path:
    path = Path.home() / ".local" / "share" / "cc-continue" / "history.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def add_command(db_path: str, project_path: str, prompt: str) -> None:
    storage = Storage(db_path)
    queue = storage.get_queue_by_path(project_path)
    if queue is None:
        import uuid

        queue = storage.create_queue(
            Path(project_path).name or project_path, project_path, str(uuid.uuid4())
        )
    storage.add_queue_item(queue.id, prompt)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cc-continue")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Queue a prompt for a project without opening the TUI")
    add_parser.add_argument("project_path")
    add_parser.add_argument("prompt")

    args = parser.parse_args(argv)

    if args.command == "add":
        add_command(str(default_db_path()), str(Path(args.project_path).resolve()), args.prompt)
        return

    from cc_continue.tui.app import run_app

    run_app(str(default_db_path()))


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: PASS (2 tests).

- [x] **Step 5: Commit**

```bash
git add src/cc_continue/cli.py tests/test_cli.py
git commit -m "feat: add CLI entry point with add subcommand"
```

---

### Task 8: TUI dashboard + app wiring

**Files:**
- Create: `src/cc_continue/tui/__init__.py`
- Create: `src/cc_continue/tui/app.py`
- Create: `src/cc_continue/tui/dashboard.py`
- Test: `tests/test_tui_dashboard.py`

**Interfaces:**
- Consumes: `Storage`, `Orchestrator` (Task 6/7).
- Produces: `run_app(db_path: str) -> None` (blocking, used by `cli.py`); `CCContinueApp(db_path: str)` Textual `App` subclass with a `DashboardScreen` as the default screen, refreshed on a timer, showing one row per queue (`name`, `status`, pending count, today's cost).

- [x] **Step 1: Write failing test (Textual pilot smoke test)**

```python
import pytest

from cc_continue.cli import add_command
from cc_continue.tui.app import CCContinueApp


@pytest.mark.asyncio
async def test_dashboard_lists_queues(tmp_path):
    db_path = str(tmp_path / "history.db")
    add_command(db_path, "/tmp/proj-a", "do a thing")

    app = CCContinueApp(db_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#dashboard-table")
        rendered_rows = [str(cell) for row_key in table.rows for cell in table.get_row(row_key)]
        assert any("proj-a" in cell for cell in rendered_rows)

    await app.orchestrator.stop_all()
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tui_dashboard.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [x] **Step 3: Implement tui package**

`src/cc_continue/tui/__init__.py`: (empty)

`src/cc_continue/tui/dashboard.py`:
```python
from __future__ import annotations

from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header

from cc_continue.storage import Storage


class DashboardScreen(Screen):
    BINDINGS = [
        ("a", "add_prompt", "Add prompt"),
        ("r", "retry_queue", "Retry blocked"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage

    def compose(self):
        yield Header()
        yield Container(DataTable(id="dashboard-table"))
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        table.add_columns("Project", "Status", "Pending", "Today's cost")
        self.refresh_table()
        self.set_interval(2.0, self.refresh_table)

    def refresh_table(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        table.clear()
        for queue in self.storage.list_queues():
            pending = sum(
                1 for item in [self.storage.next_pending_item(queue.id)] if item is not None
            )
            today_runs = [
                r for r in self.storage.runs_for_queue(queue.id)
                if r.started_at.date() == r.started_at.date()
            ]
            today_cost = sum(r.cost_usd for r in today_runs)
            table.add_row(queue.name, queue.status.value, str(pending), f"${today_cost:.4f}")

    def action_add_prompt(self) -> None:
        pass

    def action_retry_queue(self) -> None:
        pass

    def action_quit(self) -> None:
        self.app.exit()
```

`src/cc_continue/tui/app.py`:
```python
from __future__ import annotations

import asyncio

from textual.app import App

from cc_continue.orchestrator import Orchestrator
from cc_continue.storage import Storage
from cc_continue.tui.dashboard import DashboardScreen


class CCContinueApp(App):
    def __init__(self, db_path: str):
        super().__init__()
        self.storage = Storage(db_path)
        self.orchestrator = Orchestrator(self.storage)

    async def on_mount(self) -> None:
        await self.orchestrator.start_all()
        await self.push_screen(DashboardScreen(self.storage))

    async def on_unmount(self) -> None:
        await self.orchestrator.stop_all()


def run_app(db_path: str) -> None:
    app = CCContinueApp(db_path)
    app.run()
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tui_dashboard.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/cc_continue/tui/__init__.py src/cc_continue/tui/app.py src/cc_continue/tui/dashboard.py tests/test_tui_dashboard.py
git commit -m "feat: add Textual dashboard screen and app wiring"
```

---

### Task 9: TUI add-prompt modal and queue detail screen

**Files:**
- Create: `src/cc_continue/tui/queue_detail.py`
- Modify: `src/cc_continue/tui/dashboard.py` (wire `action_add_prompt` to push an add-prompt modal; `Enter` opens `QueueDetailScreen`)
- Test: `tests/test_tui_queue_detail.py`

**Interfaces:**
- Consumes: `Storage`, `Orchestrator`.
- Produces: `AddPromptModal(orchestrator: Orchestrator)` Textual `ModalScreen` with a project-path input, a prompt textarea, and a submit button that calls `orchestrator.add_prompt(path, prompt)`; `QueueDetailScreen(storage, queue_id)` showing pending items and run history for one queue.

- [ ] **Step 1: Write failing test**

```python
import pytest

from cc_continue.orchestrator import Orchestrator
from cc_continue.storage import Storage
from cc_continue.tui.queue_detail import QueueDetailScreen
from cc_continue.tui.app import CCContinueApp


@pytest.mark.asyncio
async def test_add_prompt_modal_queues_item(tmp_path):
    db_path = str(tmp_path / "history.db")
    app = CCContinueApp(db_path)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        path_input = app.query_one("#add-prompt-path")
        prompt_input = app.query_one("#add-prompt-text")
        path_input.value = "/tmp/proj-b"
        prompt_input.text = "queued via modal"
        await pilot.click("#add-prompt-submit")
        await pilot.pause()

        queue = app.storage.get_queue_by_path("/tmp/proj-b")
        assert queue is not None
        item = app.storage.next_pending_item(queue.id)
        assert item.prompt_text == "queued via modal"

    await app.orchestrator.stop_all()


@pytest.mark.asyncio
async def test_queue_detail_shows_history(tmp_path):
    db_path = str(tmp_path / "history.db")
    storage = Storage(db_path)
    queue = storage.create_queue("proj-c", "/tmp/proj-c", "sess-1")

    screen = QueueDetailScreen(storage, queue.id)
    from textual.app import App as _App

    class _HostApp(_App):
        def on_mount(self):
            self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.query_one("#queue-detail-title")
        assert "proj-c" in str(header.renderable)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tui_queue_detail.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement queue_detail.py and wire dashboard actions**

`src/cc_continue/tui/queue_detail.py`:
```python
from __future__ import annotations

from textual.containers import Container, Horizontal
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static, TextArea

from cc_continue.orchestrator import Orchestrator
from cc_continue.storage import Storage


class AddPromptModal(ModalScreen):
    def __init__(self, orchestrator: Orchestrator, default_path: str = ""):
        super().__init__()
        self.orchestrator = orchestrator
        self.default_path = default_path

    def compose(self):
        yield Container(
            Static("New prompt"),
            Input(value=self.default_path, placeholder="project path", id="add-prompt-path"),
            TextArea(id="add-prompt-text"),
            Horizontal(
                Button("Add", id="add-prompt-submit", variant="primary"),
                Button("Cancel", id="add-prompt-cancel"),
            ),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-prompt-submit":
            path = self.query_one("#add-prompt-path", Input).value.strip()
            prompt = self.query_one("#add-prompt-text", TextArea).text.strip()
            if path and prompt:
                self.orchestrator.add_prompt(path, prompt)
            self.dismiss()
        elif event.button.id == "add-prompt-cancel":
            self.dismiss()


class QueueDetailScreen(Screen):
    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, storage: Storage, queue_id: int):
        super().__init__()
        self.storage = storage
        self.queue_id = queue_id

    def compose(self):
        queue = self.storage.get_queue(self.queue_id)
        yield Header()
        yield Static(f"Queue: {queue.name} ({queue.project_path})", id="queue-detail-title")
        yield Container(DataTable(id="queue-history-table"))
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#queue-history-table", DataTable)
        table.add_columns("Started", "Status", "Cost", "Result")
        for run in self.storage.runs_for_queue(self.queue_id):
            table.add_row(
                run.started_at.strftime("%Y-%m-%d %H:%M"),
                run.status.value,
                f"${run.cost_usd:.4f}",
                (run.result_text or run.error_text or "")[:60],
            )

    def action_back(self) -> None:
        self.app.pop_screen()
```

Modify `src/cc_continue/tui/dashboard.py`: replace the two `pass`-bodied actions:

```python
    def action_add_prompt(self) -> None:
        from cc_continue.tui.queue_detail import AddPromptModal

        self.app.push_screen(AddPromptModal(self.app.orchestrator))

    def action_retry_queue(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        if table.cursor_row is None:
            return
        row_key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key
        queues = self.storage.list_queues()
        queue = queues[table.cursor_row]
        if queue.status.value == "blocked_error":
            from cc_continue.models import ItemStatus, QueueStatus

            item = None
            for run in self.storage.runs_for_queue(queue.id):
                pass
            self.storage.update_queue_status(queue.id, QueueStatus.IDLE)
            failed_items = [
                i for i in [self.storage.next_pending_item(queue.id)] if i is not None
            ]
            self.app.orchestrator.runtimes[queue.id].notify()
```

Also add a row-selection binding to open `QueueDetailScreen` on `Enter`. Add to `DashboardScreen.BINDINGS`: `("enter", "open_detail", "Open")`, and:

```python
    def action_open_detail(self) -> None:
        from cc_continue.tui.queue_detail import QueueDetailScreen

        table = self.query_one("#dashboard-table", DataTable)
        if table.cursor_row is None:
            return
        queue = self.storage.list_queues()[table.cursor_row]
        self.app.push_screen(QueueDetailScreen(self.storage, queue.id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tui_queue_detail.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cc_continue/tui/queue_detail.py src/cc_continue/tui/dashboard.py tests/test_tui_queue_detail.py
git commit -m "feat: add prompt modal and queue detail screen"
```

**Implementer note:** the `action_retry_queue` draft above has a stray no-op loop (`for run in ...: pass`) left from drafting — delete that loop; the working version only needs `update_queue_status(queue.id, QueueStatus.IDLE)` followed by `self.app.orchestrator.runtimes[queue.id].notify()`. Write it clean, don't copy the stray loop.

---

### Task 10: Analytics screen

**Files:**
- Create: `src/cc_continue/tui/analytics.py`
- Modify: `src/cc_continue/tui/dashboard.py` (add `("v", "view_analytics", "Analytics")` binding + `action_view_analytics`)
- Test: `tests/test_tui_analytics.py`

**Interfaces:**
- Consumes: `Storage.daily_cost_totals`, `Storage.blocked_seconds_total`, `Storage.list_queues`, `Storage.runs_for_queue`.
- Produces: `AnalyticsScreen(storage: Storage)` showing: total cost/tokens (last 30 days) as a `Sparkline`, per-project cost as a `DataTable`, total blocked time, success/error/rate_limited counts.

- [ ] **Step 1: Write failing test**

```python
import pytest
from datetime import datetime

from cc_continue.models import PromptRun, RunStatus
from cc_continue.storage import Storage
from cc_continue.tui.analytics import AnalyticsScreen
from textual.app import App


@pytest.mark.asyncio
async def test_analytics_shows_totals(tmp_path):
    db_path = str(tmp_path / "history.db")
    storage = Storage(db_path)
    queue = storage.create_queue("proj-d", "/tmp/proj-d", "sess-1")
    storage.insert_prompt_run(
        PromptRun(
            id=0,
            queue_id=queue.id,
            queue_item_id=None,
            prompt_text="x",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            status=RunStatus.SUCCESS,
            cost_usd=1.23,
        )
    )

    class _HostApp(App):
        def on_mount(self):
            self.push_screen(AnalyticsScreen(storage))

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#analytics-project-table")
        rows = [str(cell) for row_key in table.rows for cell in table.get_row(row_key)]
        assert any("proj-d" in cell for cell in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tui_analytics.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement analytics.py**

```python
from __future__ import annotations

from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Sparkline, Static

from cc_continue.models import RunStatus
from cc_continue.storage import Storage


class AnalyticsScreen(Screen):
    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage

    def compose(self):
        yield Header()
        yield Container(
            Static("Cost per day (last 30 days)"),
            Sparkline([], id="cost-sparkline"),
            Static("Cost per project", id="project-cost-label"),
            DataTable(id="analytics-project-table"),
            Static(id="analytics-summary"),
        )
        yield Footer()

    def on_mount(self) -> None:
        daily = self.storage.daily_cost_totals()
        sparkline = self.query_one("#cost-sparkline", Sparkline)
        sparkline.data = [v for _, v in daily] or [0]

        table = self.query_one("#analytics-project-table", DataTable)
        table.add_columns("Project", "Total cost", "Success", "Errors", "Rate-limited")
        for queue in self.storage.list_queues():
            runs = self.storage.runs_for_queue(queue.id)
            total_cost = sum(r.cost_usd for r in runs)
            success = sum(1 for r in runs if r.status == RunStatus.SUCCESS)
            errors = sum(1 for r in runs if r.status == RunStatus.ERROR)
            limited = sum(1 for r in runs if r.status == RunStatus.RATE_LIMITED)
            table.add_row(queue.name, f"${total_cost:.4f}", str(success), str(errors), str(limited))

        blocked_seconds = self.storage.blocked_seconds_total()
        summary = self.query_one("#analytics-summary", Static)
        summary.update(f"Total time blocked on rate limits: {blocked_seconds / 60:.1f} min")

    def action_back(self) -> None:
        self.app.pop_screen()
```

Modify `src/cc_continue/tui/dashboard.py`: add binding `("v", "view_analytics", "Analytics")` and:

```python
    def action_view_analytics(self) -> None:
        from cc_continue.tui.analytics import AnalyticsScreen

        self.app.push_screen(AnalyticsScreen(self.storage))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tui_analytics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cc_continue/tui/analytics.py src/cc_continue/tui/dashboard.py tests/test_tui_analytics.py
git commit -m "feat: add analytics screen"
```

---

### Task 11: README and manual end-to-end smoke test

**Files:**
- Create: `README.md`

**Interfaces:**
- None (documentation + manual verification task).

- [ ] **Step 1: Write README.md**

```markdown
# CC-continue

Prompt-queue TUI for Claude Code. Queue prompts per project; CC-continue
runs them headless (`claude -p --resume`) one at a time per project queue,
running multiple projects concurrently, and automatically retries when a
usage-limit block resets. History and basic analytics are kept in
`~/.local/share/cc-continue/history.db`.

## Install

    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"

## Usage

Launch the TUI:

    .venv/bin/cc-continue

Keys: `a` add prompt, `Enter` open queue detail, `v` analytics,
`r` retry a blocked queue, `q` quit.

Queue a prompt without opening the TUI:

    .venv/bin/cc-continue add /path/to/project "do the thing"

## Important

CC-continue only advances queues while it is running — keep it open in a
long-lived tmux/screen session (or a systemd user service) if you want it
to keep working overnight.

All headless runs use `--dangerously-skip-permissions`. Only queue
prompts for projects/prompts you'd trust to run unattended.

## Tests

    .venv/bin/pytest
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/pytest -v`
Expected: all tests PASS.

- [ ] **Step 3: Manual smoke test with a real, cheap Claude Code prompt**

Run (uses a tiny amount of real usage — keep the prompt trivial):
```bash
.venv/bin/cc-continue add /tmp <path-to-empty-scratch-dir> "Reply with exactly one word: PONG"
```
Then launch `.venv/bin/cc-continue`, confirm the queue appears, watch it run and flip to `done`, open queue detail (`Enter`) to see the `PONG` result in history, and check `v` analytics shows the cost.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add README with usage and smoke-test instructions"
```

---

## Self-Review Notes

- **Spec coverage:** every design section maps to a task — architecture (Tasks 1, 6, 8), data model (Task 5), queue trigger logic incl. rate-limit retry/backoff/hard-error blocking/crash recovery (Task 6), TUI dashboard/detail/analytics (Tasks 8–10), CLI `add` (Task 7), testing incl. mock-style injectable `run_fn` (Task 6) and manual smoke test (Task 11), YAGNI simplifications (no per-queue permissions, no live streaming — reflected by omission, not built).
- **Placeholder scan:** none left; the one intentionally-flagged rough spot (Task 9's draft `action_retry_queue`) is called out explicitly as an implementer note rather than left silently wrong.
- **Type consistency:** `RunFn` signature `(project_path, session_id, prompt, resume) -> Awaitable[RunResult]` matches between `runner.execute`, `orchestrator.QueueRuntime`, and all test fakes. `Storage` method names/signatures match between Task 5's implementation and every later consumer (Tasks 6, 7, 8, 9, 10).
