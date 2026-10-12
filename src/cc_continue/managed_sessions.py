"""Interactive Claude Code processes that cc-continue itself runs for
remote-control conversations: one tmux session per conversation on a
dedicated tmux server, so the conversation can also be driven from the
Claude mobile app / claude.ai while cc-continue types queued prompts in.

Headless `claude -p` can't do this — it silently ignores --remote-control
(verified), because remote control needs a long-lived process.
"""
from __future__ import annotations

import re
import shlex
import subprocess

from cc_continue.live_delivery import DeliveryResult
from cc_continue.models import Queue

# Separate from the user's default tmux server and from the TUI's own one.
TMUX_SOCKET = "cc-continue-sessions"

_REMOTE_URL_RE = re.compile(r"https://claude\.ai/code/session_[A-Za-z0-9]+")
_SESSION_SELECTING_FLAGS = ("--resume", "--from-pr")


def _run(args: list[str], input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, input=input_text, capture_output=True, text=True, timeout=10)


def _tmux(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess:
    return _run(["tmux", "-L", TMUX_SOCKET, *args], input_text=input_text)


def target(queue_id: int) -> str:
    return f"q{queue_id}"


def build_interactive_command(queue: Queue, has_transcript: bool) -> list[str]:
    first = list(queue.first_run_flags or [])
    if any(flag in first for flag in _SESSION_SELECTING_FLAGS):
        session = first  # fork / from-PR: they pick the session themselves
    elif has_transcript:
        session = ["--resume", queue.session_id]
    else:
        session = ["--session-id", queue.session_id]
    return ["claude", *session, "--remote-control", queue.name, *(queue.launch_flags or [])]


def is_running(queue_id: int) -> bool:
    return _tmux("has-session", "-t", target(queue_id)).returncode == 0


def start(queue: Queue, command: list[str]) -> None:
    _tmux(
        "new-session", "-d", "-s", target(queue.id), "-x", "200", "-y", "50",
        "-c", queue.project_path, shlex.join(command),
    )


def stop(queue_id: int) -> None:
    _tmux("kill-session", "-t", target(queue_id))


def capture(queue_id: int) -> str:
    result = _tmux("capture-pane", "-p", "-t", target(queue_id))
    return result.stdout if result.returncode == 0 else ""


def pane_pid(queue_id: int) -> int | None:
    result = _tmux("display-message", "-p", "-t", target(queue_id), "#{pane_pid}")
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def parse_remote_url(pane_text: str) -> str | None:
    match = _REMOTE_URL_RE.search(pane_text)
    return match.group(0) if match else None


def needs_trust_confirmation(pane_text: str) -> bool:
    """Interactive Claude asks whether to trust a new folder (headless -p
    skips it). The user picked the folder in cc-continue, so we accept."""
    lowered = pane_text.lower()
    return "do you trust" in lowered or "trust this folder" in lowered


def confirm(queue_id: int) -> None:
    _tmux("send-keys", "-t", target(queue_id), "Enter")


def paste_and_submit(queue_id: int, text: str) -> DeliveryResult:
    """Paste the prompt as ONE bracketed paste (plain send-keys would turn
    each newline into Enter and submit a multi-line prompt line by line),
    then press Enter to send it."""
    buffer = f"cc-continue-{queue_id}"
    steps = [
        (("load-buffer", "-b", buffer, "-"), text),
        (("paste-buffer", "-p", "-d", "-b", buffer, "-t", target(queue_id)), None),
        (("send-keys", "-t", target(queue_id), "Enter"), None),
    ]
    for args, input_text in steps:
        result = _tmux(*args, input_text=input_text)
        if result.returncode != 0:
            return DeliveryResult(delivered=False, error=result.stderr.strip() or f"tmux {args[0]} failed")
    return DeliveryResult(delivered=True)
