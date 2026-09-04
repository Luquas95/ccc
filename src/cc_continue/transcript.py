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
