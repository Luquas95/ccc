from __future__ import annotations

import json
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
