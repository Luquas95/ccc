from __future__ import annotations

import subprocess
from dataclasses import dataclass

from ccc.session_discovery import discover_sessions, find_tmux_pane_for_pid, session_ready_for_input


@dataclass
class DeliveryResult:
    delivered: bool
    error: str | None = None


def deliver_to_live_session(session_id: str, prompt_text: str) -> DeliveryResult:
    """Best-effort delivery of a prompt into a live interactive Claude Code
    session's own tmux pane via `tmux send-keys`, so the prompt visibly
    continues that terminal's conversation instead of running as a
    separate headless process.

    IMPORTANT — inherent risk, by design (chosen explicitly over the
    safer headless mode): this literally types into whatever the pane's
    input box currently holds. If the human is mid-typing something else
    at the exact moment this fires, the two get interleaved/garbled.
    There is no reliable way to detect "the human is currently typing" —
    only "Claude itself is idle and not blocked on a limit"
    (session_ready_for_input), which is necessary but not sufficient.

    Caller (QueueRuntime) is responsible for waiting until
    session_ready_for_input() is true before calling this — this function
    itself does not poll or wait, it makes exactly one delivery attempt.
    """
    sessions = discover_sessions()
    session = next((s for s in sessions if s.session_id == session_id), None)
    if session is None:
        return DeliveryResult(delivered=False, error="session is no longer running")
    if not session_ready_for_input(session):
        return DeliveryResult(delivered=False, error="session is not ready for input")
    if session.pid is None:
        return DeliveryResult(delivered=False, error="session has no known process id")

    pane = find_tmux_pane_for_pid(session.pid)
    if pane is None:
        return DeliveryResult(delivered=False, error="could not find a tmux pane for this session")

    return _send_keys(pane, prompt_text)


def _send_keys(pane: str, text: str) -> DeliveryResult:
    try:
        # -l: literal — don't let tmux interpret the prompt text as key
        # names/sequences. Sent as a separate call from Enter so a prompt
        # containing e.g. "C-c"-looking substrings is never misread.
        text_result = subprocess.run(
            ["tmux", "send-keys", "-t", pane, "-l", text],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if text_result.returncode != 0:
            return DeliveryResult(delivered=False, error=text_result.stderr.strip() or "tmux send-keys failed")
        enter_result = subprocess.run(
            ["tmux", "send-keys", "-t", pane, "Enter"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if enter_result.returncode != 0:
            return DeliveryResult(delivered=False, error=enter_result.stderr.strip() or "tmux send-keys Enter failed")
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return DeliveryResult(delivered=False, error=str(exc))

    return DeliveryResult(delivered=True)
