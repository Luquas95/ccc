from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class DiscoveredSession:
    session_id: str
    name: str
    cwd: str
    kind: str  # "interactive" | "background"
    status: str | None


def discover_sessions() -> list[DiscoveredSession]:
    """Live Claude Code sessions on this machine (interactive + background),
    via `claude agents --json`. Returns [] on any failure (claude not on
    PATH, no active sessions, unexpected output) — never raises, since
    this is a nice-to-have discovery aid, not load-bearing for the daemon."""
    try:
        result = subprocess.run(
            ["claude", "agents", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []

    if not isinstance(data, list):
        return []

    sessions = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        session_id = entry.get("sessionId")
        cwd = entry.get("cwd")
        if not session_id or not cwd:
            continue
        sessions.append(
            DiscoveredSession(
                session_id=session_id,
                name=entry.get("name") or session_id[:8],
                cwd=cwd,
                kind=entry.get("kind", "interactive"),
                status=entry.get("status"),
            )
        )
    return sessions
