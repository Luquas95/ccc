"""The Claude Code pane next to ccc: an interactive conversation's real
CLI, shown in a tmux pane split off ccc's own window (ccc itself runs in
tmux — the ccc-tui service). Nothing is emulated: the pane is a nested
tmux client attached to the conversation's session on the ccc-sessions
server (see attach_cli), so every Claude Code feature works.

Only one such pane exists; it's marked with the @ccc-cli pane option
holding the conversation (queue) id it shows."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys

PANE_OPTION = "@ccc-cli"
# ccc keeps this many columns (its sidebar) while the pane is open.
SIDEBAR_COLUMNS = 34
# Narrower windows (phone): the pane takes the whole window when focused.
NARROW_COLUMNS = 100
# ccc's own tmux server (bin/ccc-tui-supervise.sh) — only there do we
# change session options such as the mouse.
CCC_SOCKET = "ccc"


def available() -> bool:
    """True when ccc runs inside tmux, so it can split its window."""
    return bool(os.environ.get("TMUX") and os.environ.get("TMUX_PANE"))


def _own_pane() -> str:
    return os.environ["TMUX_PANE"]


def _tmux(*args: str) -> subprocess.CompletedProcess:
    # Plain `tmux`: $TMUX points it at the server ccc runs in.
    return subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=5)


def attach_command(queue_id: int) -> str:
    return shlex.join([sys.executable, "-m", "ccc.attach_cli", str(queue_id)])


def find() -> tuple[str, int] | None:
    """(pane id, queue id) of the open Claude Code pane, if any."""
    result = _tmux("list-panes", "-t", _own_pane(), "-F", f"#{{pane_id}} #{{{PANE_OPTION}}}")
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        pane, _, queue = line.partition(" ")
        if queue.strip().isdigit():
            return pane, int(queue)
    return None


def _window_width() -> int:
    result = _tmux("display-message", "-p", "-t", _own_pane(), "#{window_width}")
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def _on_ccc_server() -> bool:
    return os.path.basename(os.environ.get("TMUX", "").split(",")[0]) == CCC_SOCKET


def open(queue_id: int) -> str | None:
    """Show the conversation in the pane (create it, or switch what it
    shows). Returns the pane id, None if tmux refused."""
    command = attach_command(queue_id)
    current = find()
    if current is not None:
        pane, shown = current
        if shown == queue_id:
            return pane
        if _tmux("respawn-pane", "-k", "-t", pane, command).returncode != 0:
            return None
    else:
        width = max(20, _window_width() - SIDEBAR_COLUMNS - 1)
        result = _tmux("split-window", "-h", "-d", "-l", str(width), "-t", _own_pane(),
                       "-P", "-F", "#{pane_id}", command)
        if result.returncode != 0:
            return None
        pane = result.stdout.strip()
        if _on_ccc_server():
            # Click a pane to switch to it; the wheel scrolls Claude.
            _tmux("set-option", "-t", _own_pane(), "mouse", "on")
    _tmux("set-option", "-p", "-t", pane, PANE_OPTION, str(queue_id))
    return pane


def focus() -> None:
    """Put the keyboard into the Claude Code pane (whole window when
    narrow)."""
    current = find()
    if current is None:
        return
    pane = current[0]
    _tmux("select-pane", "-t", pane)
    if 0 < _window_width() < NARROW_COLUMNS:
        _tmux("resize-pane", "-Z", "-t", pane)


def close() -> None:
    """Close the pane (Claude keeps running in its session)."""
    current = find()
    if current is not None:
        _tmux("kill-pane", "-t", current[0])
