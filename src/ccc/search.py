"""Search across all conversations' transcripts, and Markdown export."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ccc.notify import known_secrets
from ccc.redact import redact
from ccc.storage import Storage
from ccc.transcript import TranscriptEvent, find_transcript_path, parse_transcript_events

MAX_HITS = 200
SNIPPET_CHARS = 120


@dataclass
class SearchHit:
    queue_id: int
    queue_name: str
    timestamp: datetime
    kind: str  # "human" | "assistant_text"
    snippet: str


def _events(storage: Storage, queue) -> list[TranscriptEvent]:
    path = find_transcript_path(queue.session_id)
    if path is None:
        return []
    events, _ = parse_transcript_events(path)
    return events


def _snippet(text: str, start: int, length: int) -> str:
    flat = " ".join(text.split())
    # Map the match position onto the whitespace-flattened text.
    pos = len(" ".join(text[:start].split()))
    half = (SNIPPET_CHARS - length) // 2
    lo = max(0, pos - half)
    hi = min(len(flat), lo + SNIPPET_CHARS)
    lo = max(0, hi - SNIPPET_CHARS)
    return ("…" if lo > 0 else "") + flat[lo:hi] + ("…" if hi < len(flat) else "")


def search_conversations(storage: Storage, query: str, limit: int = MAX_HITS) -> list[SearchHit]:
    """Case-insensitive substring search in every conversation (archived
    too), newest messages first."""
    query = query.strip()
    if not query:
        return []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    hits: list[SearchHit] = []
    for queue in storage.list_queues():
        for event in _events(storage, queue):
            if event.kind not in ("human", "assistant_text"):
                continue
            match = pattern.search(event.text)
            if match:
                hits.append(
                    SearchHit(queue.id, queue.name, event.timestamp, event.kind,
                              _snippet(event.text, match.start(), len(query)))
                )
    hits.sort(key=lambda h: h.timestamp, reverse=True)
    return hits[:limit]


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "conversation"


def export_markdown(storage: Storage, queue_id: int, out_dir: Path) -> Path:
    queue = storage.get_queue(queue_id)
    lines = [f"# {queue.name}", "", f"`{queue.project_path}` · session `{queue.session_id}`", ""]
    for event in _events(storage, queue):
        when = event.timestamp.astimezone().strftime("%Y-%m-%d %H:%M")
        if event.kind == "human":
            lines += [f"## **You** · {when}", "", event.text, ""]
        elif event.kind == "assistant_text":
            lines += [f"## **Claude** · {when}", "", event.text, ""]
        elif event.kind == "tool_call":
            lines += [f"- ⚙ {event.text}"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{_safe_name(queue.name)}-{datetime.now():%Y%m%d-%H%M%S}.md"
    # Masked: an export is a file you share; see ccc.redact.
    path.write_text(redact("\n".join(lines) + "\n", known_secrets(storage)), encoding="utf-8")
    return path
