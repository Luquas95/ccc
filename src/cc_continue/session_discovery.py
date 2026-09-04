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
    pid: int | None = None
    state: str | None = None  # e.g. "blocked" when hard-blocked on a usage limit


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
                pid=entry.get("pid"),
                state=entry.get("state"),
            )
        )
    return sessions


def find_tmux_pane_for_pid(pid: int) -> str | None:
    """Find the tmux pane (as a "session:window.pane" target string usable
    with `tmux send-keys -t <target>`) whose shell directly launched the
    given process pid. Claude Code sessions run as a child of the pane's
    shell — confirmed by inspecting a live machine: a tmux pane's
    #{pane_pid} (its shell) is the *parent* (PPID) of the `claude` process
    pid reported by `claude agents --json`. Returns None if the pid has no
    parent (already exited, or `ps` unavailable) or no pane matches."""
    try:
        ppid_result = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ppid_result.returncode != 0:
            return None
        ppid = ppid_result.stdout.strip()
        if not ppid:
            return None

        panes_result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{session_name}:#{window_index}.#{pane_index} #{pane_pid}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if panes_result.returncode != 0:
            return None
        for line in panes_result.stdout.splitlines():
            parts = line.rsplit(" ", 1)
            if len(parts) != 2:
                continue
            target, pane_pid = parts
            if pane_pid == ppid:
                return target
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return None


def session_ready_for_input(session: DiscoveredSession) -> bool:
    """True when a discovered session looks ready to receive a fresh
    prompt: not actively generating a response, and not hard-blocked on a
    usage limit. Best-effort — Claude Code's own reported status/state,
    not a guarantee (the human could be mid-typing something else at that
    exact moment; see live_delivery module docstring)."""
    if session.status != "idle":
        return False
    if session.state == "blocked":
        return False
    return True
