# Conversation View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a split-pane "Conversations" screen to the `ccc` TUI (left: list of queues, right: that queue's full Claude Code conversation, live-updating) reachable via a new `c` keybinding on the dashboard.

**Architecture:** A new pure data-layer module (`transcript.py`) locates and incrementally parses a queue's Claude Code JSONL session transcript from `~/.claude/projects/**/<session_id>.jsonl` into a flat list of human/assistant-text/tool-call events. A new Textual screen (`conversations.py`) renders those events as bordered message boxes in a right-hand `VerticalScroll`, with a left-hand `DataTable` of queue names whose `RowHighlighted` message (fires on arrow-key movement, confirmed live — no Enter needed) switches which queue's transcript is shown, per-queue caching its file offset and rendered events so re-selecting a previously-viewed queue doesn't re-parse from scratch.

**Tech Stack:** Python 3.12, Textual (existing project dependency), stdlib `json`/`pathlib`/`glob`.

## Global Constraints

- Tool-call preview text: `<tool_name>: <json.dumps(input) truncated to 80 chars, "…" appended if longer>` — no per-tool-specific formatting.
- Message box timestamp format: `%H:%M` (local time), shown in the box for human/assistant-text events only (not tool-call lines).
- Left panel: fixed width 32 columns, one row per queue showing only `queue.name` (no status/pending — that's the dashboard's job).
- Right panel refreshes only the **currently selected** queue's transcript, every 2.0s (same cadence as `DashboardScreen.refresh_table`), never all queues at once.
- Footer/bottom bar: plain Textual `Footer()`, no custom styling in this plan.
- No transcript found for a queue → right panel shows the text `"No conversation yet."`.
- New dashboard binding: `("c", "view_conversations", "Conversations")`.

---

## File Structure

```
CC-continue/
  src/cc_continue/
    transcript.py            # NEW — pure data layer, no Textual imports
    tui/
      conversations.py       # NEW — ConversationsScreen
      dashboard.py            # MODIFY — add 'c' binding + action
  tests/
    test_transcript.py       # NEW
    test_tui_conversations.py  # NEW
```

---

### Task 1: Transcript data layer — event model and file discovery

**Files:**
- Create: `src/cc_continue/transcript.py`
- Test: `tests/test_transcript.py`

**Interfaces:**
- Produces: `TranscriptEventKind` (`Literal["human", "assistant_text", "tool_call"]` — implemented as a plain `str` constant set, not an Enum, to keep this task's public surface minimal); `TranscriptEvent` dataclass (`kind: str`, `text: str`, `timestamp: datetime`); `find_transcript_path(session_id: str) -> Path | None`. Later tasks (Task 2, Task 3) import both from `cc_continue.transcript`.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from cc_continue.transcript import TranscriptEvent, find_transcript_path


def test_transcript_event_fields():
    from datetime import datetime

    event = TranscriptEvent(kind="human", text="ahoj", timestamp=datetime(2026, 9, 4, 10, 30))
    assert event.kind == "human"
    assert event.text == "ahoj"
    assert event.timestamp == datetime(2026, 9, 4, 10, 30)


def test_find_transcript_path_locates_by_session_id(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path)
    project_dir = tmp_path / "-home-lukas-DEV-some-project"
    project_dir.mkdir()
    transcript_file = project_dir / "9219c2bb-c393-4aed-ab94-fdab69a93891.jsonl"
    transcript_file.write_text("")

    found = find_transcript_path("9219c2bb-c393-4aed-ab94-fdab69a93891")
    assert found == transcript_file


def test_find_transcript_path_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path)
    assert find_transcript_path("nonexistent-session-id") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_transcript.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'cc_continue.transcript'`)

- [ ] **Step 3: Write the implementation**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Overridable in tests via monkeypatch — real default is Claude Code's own
# transcript root, one subdirectory per project (directory name is an
# encoded project path we deliberately do NOT try to reconstruct — see
# find_transcript_path).
PROJECTS_ROOT = Path.home() / ".claude" / "projects"


@dataclass
class TranscriptEvent:
    kind: str  # "human" | "assistant_text" | "tool_call"
    text: str
    timestamp: datetime


def find_transcript_path(session_id: str) -> Path | None:
    """Locate a Claude Code session's JSONL transcript by session_id alone
    (a UUID, effectively globally unique) — robust against Claude Code's
    project-path encoding scheme (replaces every non-alphanumeric
    character with "-", confirmed live on this machine; e.g. both "/" and
    "_" in a real path both became "-"), which would be fragile to
    reconstruct by hand. Returns None if no matching file exists."""
    matches = list(PROJECTS_ROOT.glob(f"*/{session_id}.jsonl"))
    return matches[0] if matches else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_transcript.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/cc_continue/transcript.py tests/test_transcript.py
git commit -m "feat: add transcript event model and session file discovery"
```

---

### Task 2: Transcript parsing — filtering rules and incremental reads

**Files:**
- Modify: `src/cc_continue/transcript.py`
- Test: `tests/test_transcript.py`

**Interfaces:**
- Consumes: `TranscriptEvent` (Task 1).
- Produces: `parse_transcript_events(path: Path, since_byte_offset: int = 0) -> tuple[list[TranscriptEvent], int]`. Task 4 (`ConversationsScreen`) calls this directly.

- [ ] **Step 1: Write the failing tests**

```python
import json

from cc_continue.transcript import parse_transcript_events


def _line(obj: dict) -> str:
    return json.dumps(obj) + "\n"


def test_parses_human_text_turn(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(
        _line(
            {
                "type": "user",
                "message": {"role": "user", "content": "ahoj"},
                "timestamp": "2026-09-04T10:30:00.000Z",
            }
        )
    )
    events, offset = parse_transcript_events(path)
    assert len(events) == 1
    assert events[0].kind == "human"
    assert events[0].text == "ahoj"
    assert offset == path.stat().st_size


def test_skips_user_turn_with_list_content_tool_result():
    # A "user" role entry whose content is a list of blocks is Claude's
    # own tool-result feedback being fed back into the model, not
    # something the human typed — must not appear as a human turn.
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.jsonl"
        path.write_text(
            _line(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "tool_result", "content": "some output"}],
                    },
                    "timestamp": "2026-09-04T10:30:00.000Z",
                }
            )
        )
        events, _ = parse_transcript_events(path)
        assert events == []


def test_parses_assistant_text_block():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.jsonl"
        path.write_text(
            _line(
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "LIVEDELIVERY"}]},
                    "timestamp": "2026-09-04T10:31:00.000Z",
                }
            )
        )
        events, _ = parse_transcript_events(path)
        assert len(events) == 1
        assert events[0].kind == "assistant_text"
        assert events[0].text == "LIVEDELIVERY"


def test_skips_thinking_block():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.jsonl"
        path.write_text(
            _line(
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "hmm"}]},
                    "timestamp": "2026-09-04T10:31:00.000Z",
                }
            )
        )
        events, _ = parse_transcript_events(path)
        assert events == []


def test_parses_tool_use_block_with_truncated_preview():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.jsonl"
        long_command = "x" * 200
        path.write_text(
            _line(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": "Bash", "input": {"command": long_command}}
                        ],
                    },
                    "timestamp": "2026-09-04T10:31:00.000Z",
                }
            )
        )
        events, _ = parse_transcript_events(path)
        assert len(events) == 1
        assert events[0].kind == "tool_call"
        assert events[0].text.startswith("Bash: ")
        assert events[0].text.endswith("…")
        assert len(events[0].text) <= len("Bash: ") + 80 + 1


def test_skips_non_conversational_line_types():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.jsonl"
        path.write_text(
            _line({"type": "cost-state", "sessionId": "x", "totalCostUSD": 0.1})
            + _line({"type": "system", "subtype": "init"})
        )
        events, _ = parse_transcript_events(path)
        assert events == []


def test_incremental_read_resumes_from_offset():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.jsonl"
        first = _line({"type": "user", "message": {"role": "user", "content": "one"}, "timestamp": "2026-09-04T10:00:00.000Z"})
        path.write_text(first)
        events1, offset1 = parse_transcript_events(path)
        assert [e.text for e in events1] == ["one"]

        second = _line({"type": "user", "message": {"role": "user", "content": "two"}, "timestamp": "2026-09-04T10:01:00.000Z"})
        with open(path, "a") as f:
            f.write(second)

        events2, offset2 = parse_transcript_events(path, since_byte_offset=offset1)
        assert [e.text for e in events2] == ["two"]
        assert offset2 > offset1


def test_incomplete_trailing_line_not_consumed():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "t.jsonl"
        complete = _line({"type": "user", "message": {"role": "user", "content": "one"}, "timestamp": "2026-09-04T10:00:00.000Z"})
        incomplete = '{"type": "user", "message": {"role": "user", "content": "cut off'  # no trailing newline, invalid JSON
        path.write_text(complete + incomplete)

        events, offset = parse_transcript_events(path)
        assert [e.text for e in events] == ["one"]
        assert offset == len(complete.encode("utf-8"))  # stopped before the incomplete line

        # once the line is completed (e.g. by the live process finishing its write), a
        # re-parse from the same offset picks it up
        with open(path, "a") as f:
            f.write(' resumed"}, "timestamp": "2026-09-04T10:02:00.000Z"}\n')
        events2, offset2 = parse_transcript_events(path, since_byte_offset=offset)
        assert len(events2) == 1
        assert events2[0].text == "cut off resumed"
        assert offset2 == path.stat().st_size
```

**Implementer note (found running this task's test):** the original
completion string above (`'", "not": ...'`) closed the JSON object without
a `timestamp` field, which `_events_from_line` requires (returns `[]`
when missing) — `events2` would have been `[]`, not length 1. Fixed to
complete the object with a valid `timestamp` field, as shown.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_transcript.py -v`
Expected: the 8 new tests FAIL with `ImportError` / `AttributeError: module 'cc_continue.transcript' has no attribute 'parse_transcript_events'`

- [ ] **Step 3: Write the implementation**

Append to `src/cc_continue/transcript.py`:

```python
import json

TOOL_PREVIEW_MAX_CHARS = 80


def _parse_timestamp(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _events_from_line(data: dict) -> list[TranscriptEvent]:
    line_type = data.get("type")
    message = data.get("message") or {}
    raw_timestamp = data.get("timestamp")
    if not raw_timestamp:
        return []
    timestamp = _parse_timestamp(raw_timestamp)

    if line_type == "user":
        content = message.get("content")
        if isinstance(content, str):
            return [TranscriptEvent(kind="human", text=content, timestamp=timestamp)]
        return []

    if line_type == "assistant":
        content = message.get("content")
        if not isinstance(content, list):
            return []
        events = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text", "")
                if text:
                    events.append(TranscriptEvent(kind="assistant_text", text=text, timestamp=timestamp))
            elif block_type == "tool_use":
                name = block.get("name", "?")
                input_preview = json.dumps(block.get("input", {}))
                if len(input_preview) > TOOL_PREVIEW_MAX_CHARS:
                    input_preview = input_preview[:TOOL_PREVIEW_MAX_CHARS] + "…"
                events.append(
                    TranscriptEvent(kind="tool_call", text=f"{name}: {input_preview}", timestamp=timestamp)
                )
            # "thinking" and any other block type: skipped
        return events

    return []  # system, cost-state, bridge-session, mode, etc.: skipped


def parse_transcript_events(path: Path, since_byte_offset: int = 0) -> tuple[list[TranscriptEvent], int]:
    """Incrementally parse a JSONL transcript from a byte offset. Returns
    new events plus the offset to pass next time. The offset only ever
    advances past complete, successfully-parsed lines — a trailing
    incomplete line (the file may be actively written by a live Claude
    Code process) is left for the next call to pick up once it's whole."""
    events: list[TranscriptEvent] = []
    with open(path, "rb") as f:
        f.seek(since_byte_offset)
        consumed = since_byte_offset
        for raw_line in f:
            if not raw_line.endswith(b"\n"):
                break  # incomplete trailing line — do not consume
            try:
                data = json.loads(raw_line)
            except json.JSONDecodeError:
                consumed += len(raw_line)
                continue
            events.extend(_events_from_line(data))
            consumed += len(raw_line)
    return events, consumed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_transcript.py -v`
Expected: PASS (11 tests total)

- [ ] **Step 5: Commit**

```bash
git add src/cc_continue/transcript.py tests/test_transcript.py
git commit -m "feat: parse transcript events with incremental byte-offset reads"
```

---

### Task 3: Regression fixture from a real captured transcript

**Files:**
- Test: `tests/test_transcript.py`

**Interfaces:**
- Consumes: `parse_transcript_events` (Task 2). No new production code — a fixture-based regression test only.

- [ ] **Step 1: Write the test using real captured transcript shapes**

These three lines are the exact real shapes captured during earlier live
testing of this project (a human-typed prompt, and the two-block
assistant reply — thinking block trimmed down since only its presence
matters, not its content — that a real `claude -p`/live-terminal run
produces). Add to `tests/test_transcript.py`:

```python
REAL_TRANSCRIPT_JSONL = "\n".join(
    [
        json.dumps(
            {
                "parentUuid": "ed53ba40-7450-472a-8afa-78574ee6d7a5",
                "isSidechain": False,
                "promptId": "3550a5ca-3778-49d6-973b-bed1e5eb4fc9",
                "type": "user",
                "message": {"role": "user", "content": "Reply with exactly one word: LIVEDELIVERY"},
                "uuid": "b705e8a4-a01e-4f31-8fea-122ed9d1cb1c",
                "timestamp": "2026-09-04T07:52:10.929Z",
                "cwd": "/home/lukas/DEV/CC-continue",
                "sessionId": "9219c2bb-c393-4aed-ab94-fdab69a93891",
            }
        ),
        json.dumps(
            {
                "parentUuid": "b11cb09d-dd40-4e2e-857f-678e807a3f09",
                "isSidechain": False,
                "message": {
                    "model": "claude-sonnet-5",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "thinking", "thinking": "", "signature": "abc"}],
                },
                "type": "assistant",
                "uuid": "9271aa1c-dcd0-4e6f-87a9-c907c12fd19c",
                "timestamp": "2026-09-04T07:52:15.000Z",
            }
        ),
        json.dumps(
            {
                "parentUuid": "9271aa1c-dcd0-4e6f-87a9-c907c12fd19c",
                "isSidechain": False,
                "message": {
                    "model": "claude-sonnet-5",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "LIVEDELIVERY"}],
                    "stop_reason": "end_turn",
                },
                "type": "assistant",
                "uuid": "1e677807-4ce1-4254-98d4-dc6e9e426551",
                "timestamp": "2026-09-04T07:52:21.000Z",
            }
        ),
    ]
) + "\n"


def test_parses_real_captured_transcript_shape(tmp_path):
    path = tmp_path / "real.jsonl"
    path.write_text(REAL_TRANSCRIPT_JSONL)

    events, offset = parse_transcript_events(path)

    assert offset == path.stat().st_size
    assert [(e.kind, e.text) for e in events] == [
        ("human", "Reply with exactly one word: LIVEDELIVERY"),
        ("assistant_text", "LIVEDELIVERY"),
    ]
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `.venv/bin/pytest tests/test_transcript.py::test_parses_real_captured_transcript_shape -v`
Expected: PASS immediately (Task 2's implementation should already handle this shape correctly — this test exists to lock that in as a regression guard, not to drive new implementation).

If it fails, the failure tells you which assumption from Task 2 doesn't hold against real data — fix `_events_from_line` until it passes before moving on.

- [ ] **Step 3: Commit**

```bash
git add tests/test_transcript.py
git commit -m "test: lock in transcript parsing against a real captured shape"
```

---

### Task 4: ConversationsScreen — layout and static rendering

**Files:**
- Create: `src/cc_continue/tui/conversations.py`
- Test: `tests/test_tui_conversations.py`

**Interfaces:**
- Consumes: `Storage.list_queues()` (existing, returns `list[Queue]`, each with `.id: int`, `.name: str`, `.session_id: str`); `find_transcript_path`, `parse_transcript_events`, `TranscriptEvent` (Tasks 1–2).
- Produces: `ConversationsScreen(storage: Storage)` — a Textual `Screen` subclass. Task 5 wires a dashboard binding to push it.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from textual.app import App
from textual.widgets import DataTable

from cc_continue.storage import Storage
from cc_continue.tui.conversations import ConversationsScreen


@pytest.mark.asyncio
async def test_shows_queue_list_and_placeholder_for_no_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    (tmp_path / "projects").mkdir()

    storage = Storage(tmp_path / "history.db")
    storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa")

    screen = ConversationsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        table = app.screen.query_one("#conversation-queue-list", DataTable)
        rows = [str(cell) for row_key in table.rows for cell in table.get_row(row_key)]
        assert any("proj-a" in cell for cell in rows)

        right_panel_text = "\n".join(
            str(s.render()) for s in app.screen.query("#conversation-transcript Static")
        )
        assert "No conversation yet." in right_panel_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tui_conversations.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'cc_continue.tui.conversations'`)

- [ ] **Step 3: Write the implementation**

```python
from __future__ import annotations

from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from cc_continue.storage import Storage
from cc_continue.transcript import TranscriptEvent, find_transcript_path, parse_transcript_events


class ConversationsScreen(Screen):
    BINDINGS = [("escape", "back", "Back")]

    DEFAULT_CSS = """
    ConversationsScreen #conversation-queue-list {
        width: 32;
    }
    ConversationsScreen #conversation-transcript {
        width: 1fr;
    }
    ConversationsScreen .message-box {
        border: round cyan;
        padding: 0 1;
        margin-bottom: 1;
    }
    ConversationsScreen .message-box-human {
        border: round cyan;
    }
    ConversationsScreen .message-box-assistant {
        border: round green;
    }
    ConversationsScreen .message-header {
        color: $accent;
    }
    ConversationsScreen .tool-call-line {
        color: $text-muted;
    }
    """

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        # Per-queue cache: queue_id -> {"path": Path|None, "offset": int,
        # "events": list[TranscriptEvent]} so switching back to an
        # already-viewed queue doesn't re-parse its transcript from zero.
        self._cache: dict[int, dict] = {}
        self._current_queue_id: int | None = None

    def compose(self):
        yield Header()
        yield Horizontal(
            DataTable(id="conversation-queue-list"),
            VerticalScroll(id="conversation-transcript"),
        )
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#conversation-queue-list", DataTable)
        table.cursor_type = "row"
        table.add_column("Queue")
        queues = self.storage.list_queues()
        for queue in queues:
            table.add_row(queue.name)
        if queues:
            # Don't rely solely on RowHighlighted firing for the initial
            # cursor position (focus timing can vary once Header/Footer
            # siblings are present) — select the first queue explicitly
            # so the right panel is deterministically populated on open.
            await self._show_queue(queues[0].id)
        # set_interval accepts an async callback directly (confirmed live
        # with a standalone sandbox script — no run_worker wrapper needed).
        self.set_interval(2.0, self._refresh_current)

    async def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # RowHighlighted fires on arrow-key movement (confirmed live: no
        # Enter needed), unlike RowSelected which only fires on
        # Enter/click — this is what makes switching immediate, per the
        # design.
        queues = self.storage.list_queues()
        if event.cursor_row >= len(queues):
            return
        await self._show_queue(queues[event.cursor_row].id)

    async def _show_queue(self, queue_id: int) -> None:
        self._current_queue_id = queue_id
        if queue_id not in self._cache:
            queue = self.storage.get_queue(queue_id)
            path = find_transcript_path(queue.session_id)
            self._cache[queue_id] = {"path": path, "offset": 0, "events": []}
            if path is not None:
                events, offset = parse_transcript_events(path)
                self._cache[queue_id]["events"] = events
                self._cache[queue_id]["offset"] = offset
        await self._render_transcript(queue_id)

    async def _render_transcript(self, queue_id: int) -> None:
        container = self.query_one("#conversation-transcript", VerticalScroll)
        await container.remove_children()
        events: list[TranscriptEvent] = self._cache[queue_id]["events"]
        if not events:
            await container.mount(Static("No conversation yet."))
            return
        for event in events:
            await container.mount(self._render_event(event))

    def _render_event(self, event: TranscriptEvent) -> Static:
        if event.kind == "tool_call":
            return Static(f"⚙ {event.text}", classes="tool-call-line")
        label = "You" if event.kind == "human" else "Claude"
        box_class = "message-box-human" if event.kind == "human" else "message-box-assistant"
        time_str = event.timestamp.strftime("%H:%M")
        return Static(f"[b]{label}[/b]  [dim]{time_str}[/dim]\n{event.text}", classes=f"message-box {box_class}")

    async def _refresh_current(self) -> None:
        if self._current_queue_id is None:
            return
        queue_id = self._current_queue_id
        cached = self._cache.get(queue_id)
        if cached is None or cached["path"] is None:
            return
        new_events, new_offset = parse_transcript_events(cached["path"], since_byte_offset=cached["offset"])
        if new_events:
            cached["events"].extend(new_events)
            cached["offset"] = new_offset
            await self._render_transcript(queue_id)

    def action_back(self) -> None:
        self.app.pop_screen()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tui_conversations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cc_continue/tui/conversations.py tests/test_tui_conversations.py
git commit -m "feat: add ConversationsScreen with split-pane queue list and transcript view"
```

---

### Task 5: Live transcript content, queue switching, and dashboard wiring

**Files:**
- Modify: `src/cc_continue/tui/conversations.py` (no changes expected — this task is tests + dashboard wiring only, listed here in case Task 4's implementation needs adjustment to satisfy these tests)
- Modify: `src/cc_continue/tui/dashboard.py`
- Test: `tests/test_tui_conversations.py`, `tests/test_tui_dashboard.py`

**Interfaces:**
- Consumes: `ConversationsScreen` (Task 4).
- Produces: nothing new consumed by later tasks — this is the final integration task.

- [ ] **Step 1: Write the failing tests**

Add `import json` to the top of `tests/test_tui_conversations.py` (Task 4's
version of this file doesn't need it; these new tests build JSONL content
with `json.dumps`), then add these two tests to the same file:

```python
@pytest.mark.asyncio
async def test_renders_real_conversation_and_switches_on_arrow_key(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    project_dir = tmp_path / "projects" / "-tmp-proj-a"
    project_dir.mkdir(parents=True)

    storage = Storage(tmp_path / "history.db")
    queue_a = storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa")
    queue_b = storage.create_queue("proj-b", "/tmp/proj-b", "session-bbb")

    transcript_a = project_dir / "session-aaa.jsonl"
    transcript_a.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": "ahoj z A"},
                "timestamp": "2026-09-04T10:00:00.000Z",
            }
        )
        + "\n"
    )

    screen = ConversationsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        def right_panel_text():
            return "\n".join(str(s.render()) for s in app.screen.query("#conversation-transcript Static"))

        assert "ahoj z A" in right_panel_text()

        await pilot.press("down")
        await pilot.pause()

        assert "No conversation yet." in right_panel_text()
        assert "ahoj z A" not in right_panel_text()


@pytest.mark.asyncio
async def test_picks_up_new_transcript_lines_on_periodic_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    project_dir = tmp_path / "projects" / "-tmp-proj-a"
    project_dir.mkdir(parents=True)

    storage = Storage(tmp_path / "history.db")
    storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa")

    transcript_a = project_dir / "session-aaa.jsonl"
    transcript_a.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "first"}, "timestamp": "2026-09-04T10:00:00.000Z"})
        + "\n"
    )

    screen = ConversationsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        with open(transcript_a, "a") as f:
            f.write(
                json.dumps({"type": "user", "message": {"role": "user", "content": "second"}, "timestamp": "2026-09-04T10:01:00.000Z"})
                + "\n"
            )

        # directly invoke the refresh instead of sleeping 2 real seconds
        await screen._refresh_current()
        await pilot.pause()

        right_panel_text = "\n".join(str(s.render()) for s in app.screen.query("#conversation-transcript Static"))
        assert "first" in right_panel_text
        assert "second" in right_panel_text
```

Add to `tests/test_tui_dashboard.py`:

```python
@pytest.mark.asyncio
async def test_pressing_c_opens_conversations_screen(tmp_path):
    db_path = str(tmp_path / "history.db")
    project_dir = tmp_path / "proj-a"
    project_dir.mkdir()
    add_command(db_path, str(project_dir), "do a thing")

    app = CCContinueApp(db_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()

        from cc_continue.tui.conversations import ConversationsScreen

        assert isinstance(app.screen, ConversationsScreen)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_tui_conversations.py tests/test_tui_dashboard.py -v`
Expected: the three new tests FAIL — the dashboard one with `AssertionError` (no such screen, since 'c' is unbound), the conversations ones may already PASS if Task 4's implementation is correct (that's fine, they still serve as regression coverage — but run them to confirm before moving on).

- [ ] **Step 3: Wire the dashboard binding**

In `src/cc_continue/tui/dashboard.py`, add to `BINDINGS` (after the existing `"s"` entry):

```python
        ("c", "view_conversations", "Conversations"),
```

Add a new action method (near `action_view_analytics`):

```python
    def action_view_conversations(self) -> None:
        from cc_continue.tui.conversations import ConversationsScreen

        self.app.push_screen(ConversationsScreen(self.storage))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_tui_conversations.py tests/test_tui_dashboard.py -v`
Expected: PASS. If either new `test_tui_conversations.py` test fails, the failure will point at a specific gap in Task 4's `ConversationsScreen` (e.g. `_show_queue` not resetting `events`/`offset` correctly per queue, or `_refresh_current` not re-rendering) — fix `conversations.py` directly, these tests are the actual spec for that behavior.

- [ ] **Step 5: Commit**

```bash
git add src/cc_continue/tui/dashboard.py tests/test_tui_conversations.py tests/test_tui_dashboard.py
git commit -m "feat: wire conversations screen to dashboard 'c' key, verify live refresh"
```

---

### Task 6: Full test suite, live visual verification, and README

**Files:**
- Modify: `README.md`

**Interfaces:** None — verification and documentation only.

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest -q`
Expected: all tests PASS (89 existing + this plan's new tests).

- [ ] **Step 2: Live visual check in an isolated tmux pane**

This screen's box/color layout is exactly the kind of thing that can look
fine in widget-region introspection but render broken on screen (see this
project's git history: the Pro-usage gauges shipped with unconstrained
widths that pushed content off-screen, only caught by actually looking at
a live pane) — so don't skip this step.

```bash
tmux kill-session -t cc-debug 2>/dev/null
tmux new-session -d -s cc-debug -x 200 -y 50 -c /home/lukas/DEV/CC-continue
tmux send-keys -t cc-debug ".venv/bin/cc-continue" Enter
sleep 2
tmux send-keys -t cc-debug "c"
sleep 2
tmux capture-pane -t cc-debug -p
```

Expected: a two-column layout — left column a narrow list of queue names,
right column either "No conversation yet." or bordered message boxes for
queues that have real prompt_runs history (from this project's own
earlier live testing). Fix any layout issue found (most likely cause,
per precedent: a `Static`/container missing an explicit width, letting it
stretch and push the other pane off-screen — add explicit `width`/`1fr`
CSS rules to fix, same pattern already used in this file's `DEFAULT_CSS`).

```bash
tmux kill-session -t cc-debug 2>/dev/null
```

- [ ] **Step 3: Update README**

In `README.md`, in the "TUI keys" line, change:

```
TUI keys: `a` add prompt, `s` live sessions, `Enter` open queue detail /
attach to a session, `v` analytics, `r` retry a blocked queue (daemon
picks it back up within ~5s), `q` quit (just closes the viewer — queued
work is unaffected).
```

to:

```
TUI keys: `a` add prompt, `s` live sessions, `c` conversations, `Enter`
open queue detail / attach to a session, `v` analytics, `r` retry a
blocked queue (daemon picks it back up within ~5s), `q` quit (just closes
the viewer — queued work is unaffected).
```

Add a new subsection after "### Two delivery modes":

```markdown
### Conversations view

Press `c` on the dashboard to see a queue's full conversation — not just
the last result. Arrow keys in the left-hand queue list immediately
switch which queue's transcript is shown on the right. This reads Claude
Code's own JSONL session transcript
(`~/.claude/projects/**/<session_id>.jsonl`) directly, so it works
identically for headless and live-terminal queues, and stays live: while
the screen is open, the currently-shown queue's transcript is re-checked
every ~2s for new messages (e.g. from a live-terminal session someone is
actively typing in).
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document the conversations view"
```

---

## Self-Review Notes

- **Spec coverage:** data model + file discovery (Task 1), filtering rules for all five line-shape cases from the spec's "Zjištění" section (Task 2), real-data regression fixture (Task 3), split-pane layout + placeholder text + box styling (Task 4), immediate arrow-key switching via `RowHighlighted` (confirmed live before writing this plan — see below) + per-queue caching + 2s live refresh of only the current queue + dashboard `c` binding (Task 5), visual verification in a real tmux pane + README (Task 6). Every requirement in the design spec maps to a task.
- **Placeholder scan:** none found.
- **Type consistency:** `TranscriptEvent(kind, text, timestamp)` used identically across Tasks 1–5. `find_transcript_path(session_id: str) -> Path | None` and `parse_transcript_events(path: Path, since_byte_offset: int = 0) -> tuple[list[TranscriptEvent], int]` signatures match between their Task 1/2 definitions and every later call site (Task 4's `_show_queue`/`_refresh_current`, Task 5's tests).
- **Pre-verified assumptions (standalone sandbox scripts run before writing this plan, not guessed):**
  1. `DataTable.RowHighlighted` (not `RowSelected`) fires on arrow-key movement without Enter (mount → row 0 highlighted automatically; each `down` press → next row highlighted) — de-risks Task 4/5's core interaction, the same category of Textual-API assumption that broke silently earlier in this project (`RowSelected` never fired from a screen-level `BINDINGS` "enter" entry).
  2. `Screen.set_interval()` accepts an async callback directly and Textual invokes it correctly — confirmed with a standalone timer test (6 calls over 0.3s at a 0.05s interval), so `_refresh_current` is registered directly with `set_interval`, no `run_worker` wrapper needed.
- **Async/await consistency fix made during self-review:** the first draft of Task 4 had `_show_queue`/`_render_transcript`/`on_data_table_row_highlighted` call `container.mount()`/`remove_children()` synchronously (without `await`), inconsistent with this codebase's own established pattern in `analytics.py` (`refresh_pro_usage` always awaits both). Reworked the whole chain (`on_mount` → `_show_queue` → `_render_transcript`) to be `async`/`await`-consistent throughout, and made `on_mount` explicitly select the first queue rather than relying on `RowHighlighted` firing reliably at mount time once `Header`/`Footer` siblings are present (verified only in a trivial single-widget sandbox app, not this screen's actual composition) — removes a timing assumption that wasn't fully verified for the real layout.
