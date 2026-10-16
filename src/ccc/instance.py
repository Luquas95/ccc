"""One ccc for everyone: the TUI runs once, in the "ccc" tmux session on
ccc's own tmux server (the ccc-tui service keeps it alive). `ccc` just
attaches to it — from any terminal, local or over SSH, you get that same
instance and the same screen; it never starts a second one."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

# Overridable so tests (and a second, separate ccc) never touch the real one.
TMUX_SOCKET = os.environ.get("CCC_TMUX_SOCKET", "ccc")
SESSION = "ccc"
PROJECT_DIR = Path(__file__).resolve().parents[2]


def tui_command() -> list[str]:
    """What the session runs: the TUI itself (`ccc tui`)."""
    return [sys.executable, "-m", "ccc.cli", "tui"]


def tui_loop() -> str:
    # Quitting the TUI brings it back a second later; the session (and so
    # the one instance) never goes away.
    return f"while true; do {shlex.join(tui_command())}; sleep 1; done"


def inside_ccc_tmux() -> bool:
    """True inside ccc's own tmux server — there `ccc` is the instance."""
    socket = os.environ.get("TMUX", "").split(",")[0]
    return bool(socket) and os.path.basename(socket) == TMUX_SOCKET


def _tmux(*args: str) -> list[str]:
    # -f /dev/null: no user tmux.conf (plugins like tmux-continuum would
    # restore the user's sessions into this server).
    return ["tmux", "-L", TMUX_SOCKET, "-f", "/dev/null", *args]


def running() -> bool:
    return subprocess.run(_tmux("has-session", "-t", SESSION), capture_output=True).returncode == 0


def attach_command() -> list[str]:
    if running():
        return _tmux("attach-session", "-t", SESSION)
    # Not running (service not installed / stopped): start it the way the
    # service does, attached.
    return _tmux("new-session", "-s", SESSION, "-c", str(PROJECT_DIR), tui_loop())


def attach() -> None:
    """Replace this process with a tmux client of the one ccc. From inside
    another tmux it nests on purpose (TMUX unset): a client can't switch
    across tmux servers."""
    command = attach_command()
    env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
    os.execvpe(command[0], command, env)
