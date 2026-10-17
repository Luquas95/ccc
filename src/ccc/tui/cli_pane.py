"""The Claude Code pane next to ccc: an interactive conversation's real
CLI, shown in a tmux pane split off ccc's own window (ccc itself runs in
tmux — the ccc-tui service). Nothing is emulated: the pane is a nested
tmux client attached to the conversation's session on the ccc-sessions
server (see attach_cli), so every Claude Code feature works.

Only one such pane exists; it's marked with the @ccc-cli pane option
holding the conversation (queue) id it shows. In the same column as the
Claude Code pane, above it, runs the bar (cli_bar: preset prompts and keys;
@ccc-bar). On
ccc's own tmux server the keys that switch between ccc and Claude and run
ccc's presets are bound while the pane is open — see key_bindings()."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys

from ccc import instance

PANE_OPTION = "@ccc-cli"
BAR_OPTION = "@ccc-bar"
# ccc's key list as a 1-row pane under everything (footer_strip).
STRIP_OPTION = "@ccc-strip"
TITLE_OPTION = "@ccc-title"
# Rows of the bar under Claude Code: preset prompts, keys.
BAR_ROWS = 2
# Keys bound on ccc's server while the pane is open (root table: they
# work in every pane, before the pane's program sees them). None of them
# is a Claude Code key: Alt+digits and Ctrl+P are unused there; Tab
# (autocomplete), Ctrl+T (to-dos) and Ctrl+D (exit) are Claude's.
SWITCH_KEY = "M-0"
PRESET_KEYS = tuple(f"M-{n}" for n in range(1, 10))
SETTINGS_KEY = "C-p"
# On ccc's own server: a title bar on each pane, and the pane you type in
# marked — otherwise nothing shows whether keys go to ccc or to Claude.
BORDER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("pane-border-status", "top"),
    ("pane-border-format",
     f"#{{?pane_active,#[fg=black#,bg=green#,bold] ⌨ typing here #[default],}} #{{{TITLE_OPTION}}} "),
    ("pane-active-border-style", "fg=green,bold"),
    ("pane-border-style", "fg=brightblack"),
)
# ccc keeps exactly its sidebar (layout.SHARED_CSS #sidebar width) while
# the pane is open, so the menu doesn't move or change size.
SIDEBAR_COLUMNS = 32
# Narrower windows (phone): the pane takes the whole window when focused.
NARROW_COLUMNS = 100
# ccc's own tmux server (bin/ccc-tui-supervise.sh) — only there do we
# change session options such as the mouse.
CCC_SOCKET = instance.TMUX_SOCKET


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


def bar_command(db_path: str) -> str:
    return shlex.join([sys.executable, "-m", "ccc.tui.cli_bar", str(db_path)])


def key_bindings(main: str, cli: str, queue_id: int, db_path: str) -> list[tuple[str, ...]]:
    """tmux commands binding ccc's keys for the open Claude Code pane:
    - Alt+0 switches between ccc (`main`) and Claude (`cli`; on narrow
      windows Claude then takes the whole window),
    - Alt+1 … Alt+9 type a preset into Claude (`ccc preset`); in ccc's
      own pane they go to ccc as before,
    - Ctrl+P opens ccc's Settings from anywhere."""
    in_ccc = f"#{{==:#{{pane_id}},{main}}}"
    # e|<| compares numbers; plain #{<:} compares strings ("80" > "100").
    to_claude = f"select-pane -t {cli} ; if-shell -F '#{{e|<|:#{{window_width}},{NARROW_COLUMNS}}}' 'resize-pane -Z -t {cli}'"
    bindings = [("bind-key", "-n", SWITCH_KEY, "if-shell", "-F", in_ccc, to_claude, f"select-pane -t {main}")]
    for number, key in enumerate(PRESET_KEYS, start=1):
        preset = shlex.join([sys.executable, "-m", "ccc.cli", "preset", str(number),
                             "--queue", str(queue_id), "--db", str(db_path)])
        # Errors are shown on the client that pressed the key, on this server.
        bindings.append((
            "bind-key", "-n", key, "if-shell", "-F", in_ccc, f"send-keys {key}",
            f"run-shell -b \"{preset} --client '#{{client_tty}}' --socket '#{{socket_path}}'\"",
        ))
    bindings.append(("bind-key", "-n", SETTINGS_KEY, "if-shell", "-F", in_ccc, f"send-keys {SETTINGS_KEY}",
                     f"select-pane -t {main} ; send-keys -t {main} {SETTINGS_KEY}"))
    return bindings


def fit_command(main: str, bar: str | None, strip: str | None = None, sidebar: bool = True) -> str:
    """tmux command putting the layout back: ccc at its sidebar width (with
    Claude Code open), the bar and the key strip at their rows. tmux
    rescales panes proportionally when the window changes size (e.g.
    attaching from a phone, then a desktop), so this runs from the
    window-resized hook too."""
    commands = [f"resize-pane -t {main} -x {SIDEBAR_COLUMNS}"] if sidebar else []
    if bar is not None:
        commands.append(f"resize-pane -t {bar} -y {BAR_ROWS}")
    if strip is not None:
        commands.append(f"resize-pane -t {strip} -y 1")
    return " ; ".join(commands)


def strip_command(main: str) -> str:
    return shlex.join([sys.executable, "-m", "ccc.tui.footer_strip", main])


def _find_flag(option: str) -> str | None:
    result = _tmux("list-panes", "-t", _own_pane(), "-F", f"#{{pane_id}} #{{{option}}}")
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        pane, _, flag = line.partition(" ")
        if flag.strip() == "1":
            return pane
    return None


def find_strip() -> str | None:
    return _find_flag(STRIP_OPTION)


def ensure_strip() -> str | None:
    """The key strip under the window (created once; it survives TUI
    restarts in the same window)."""
    strip = find_strip()
    if strip is None:
        result = _tmux("split-window", "-v", "-f", "-d", "-l", "1", "-t", _own_pane(),
                       "-P", "-F", "#{pane_id}", strip_command(_own_pane()))
        if result.returncode != 0:
            return None
        strip = result.stdout.strip()
        _tmux("set-option", "-p", "-t", strip, STRIP_OPTION, "1")
        _tmux("set-option", "-p", "-t", strip, TITLE_OPTION, "ccc · keys")
    _tmux("resize-pane", "-t", strip, "-y", "1")
    if find() is None:
        _tmux("set-hook", "-w", "-t", _own_pane(), "window-resized",
              fit_command(_own_pane(), None, strip, sidebar=False))
    return strip


def unbind_keys() -> None:
    for key in (SWITCH_KEY, *PRESET_KEYS, SETTINGS_KEY):
        _tmux("unbind-key", "-n", key)


def find_bar() -> str | None:
    return _find_flag(BAR_OPTION)


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


# Copy & paste on ccc's server, the same in ccc and in Claude Code:
# - selecting with the mouse copies to your device's clipboard (OSC 52,
#   over SSH too — Termux and Linux terminals support it) when you let
#   go; the pane leaves copy mode, so typing and pasting go to it again;
# - Ctrl+Shift+C copies the selection; without one it does nothing (it
#   must never reach Claude as Ctrl+C = interrupt);
# - Ctrl+Shift+V pastes the last copy (where the terminal doesn't paste
#   by itself — Linux terminals do, from the clipboard).
# set-clipboard stays "external" (tmux's default): only tmux's own copies
# reach the clipboard, never an escape sequence printed into a pane (a
# traceback quoting a conversation name, say). Copies made in Claude Code
# come in as a command instead (clipboard_bridge: load-buffer -w).
CLIPBOARD_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("set-option", "-s", "set-clipboard", "external"),
    ("set-option", "-s", "extended-keys", "on"),
    ("set-option", "-as", "terminal-features", ",*:clipboard:extkeys"),
    *[("bind-key", "-T", table, "MouseDragEnd1Pane", "send-keys", "-X", "copy-pipe-and-cancel")
      for table in ("copy-mode", "copy-mode-vi")],
    *[("bind-key", "-T", table, "C-S-c", "send-keys", "-X", "copy-pipe-and-cancel")
      for table in ("copy-mode", "copy-mode-vi")],
    ("bind-key", "-n", "C-S-c", "if-shell", "-F", "#{pane_in_mode}", "send-keys -X copy-pipe-and-cancel", ""),
    ("bind-key", "-n", "C-S-v", "paste-buffer", "-p"),
    # Ctrl+Q closes ccc for the terminal that pressed it: detach that
    # client (ccc keeps running; `ccc` opens it again). Quitting the TUI
    # would only restart it. Not a Claude Code key.
    ("bind-key", "-n", "C-q", "detach-client"),
)


def style_window() -> None:
    """On ccc's own server: pane title bars (and the mouse) from the start,
    not only once Claude Code opens — a title row appearing and staying
    would shift all of ccc down by a row when switching views."""
    if not (available() and _on_ccc_server()):
        return
    # Click a pane to switch to it; the wheel scrolls Claude.
    _tmux("set-option", "-t", _own_pane(), "mouse", "on")
    for name, value in BORDER_OPTIONS:
        _tmux("set-option", "-w", "-t", _own_pane(), name, value)
    _tmux("set-option", "-p", "-t", _own_pane(), TITLE_OPTION, "ccc")
    for command in CLIPBOARD_COMMANDS:
        _tmux(*command)
    ensure_strip()


def open(queue_id: int, title: str = "", db_path: str | None = None) -> str | None:
    """Show the conversation in the pane (create it, or switch what it
    shows) and, with db_path, the bar under it. Returns the pane id, None
    if tmux refused."""
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
        style_window()
    _tmux("set-option", "-p", "-t", pane, PANE_OPTION, str(queue_id))
    _tmux("set-option", "-p", "-t", pane, TITLE_OPTION, f"Claude Code · {title}" if title else "Claude Code")
    if db_path is not None and find_bar() is None:
        # -b: above Claude Code, in its column — ccc's column stays as is.
        result = _tmux("split-window", "-v", "-b", "-d", "-l", str(BAR_ROWS), "-t", pane,
                       "-P", "-F", "#{pane_id}", bar_command(db_path))
        if result.returncode == 0:
            bar = result.stdout.strip()
            _tmux("set-option", "-p", "-t", bar, BAR_OPTION, "1")
            _tmux("set-option", "-p", "-t", bar, TITLE_OPTION, "ccc · presets & keys")
    if _on_ccc_server() and db_path is not None:
        for binding in key_bindings(_own_pane(), pane, queue_id, db_path):
            _tmux(*binding)
    bar = find_bar()
    _tmux("set-hook", "-w", "-t", _own_pane(), "window-resized", fit_command(_own_pane(), bar, find_strip()))
    # And now: split-window -l counts the border row too, the bar got 1 row.
    _tmux("resize-pane", "-t", _own_pane(), "-x", str(SIDEBAR_COLUMNS))
    if bar is not None:
        _tmux("resize-pane", "-t", bar, "-y", str(BAR_ROWS))
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
    """Close the pane and its bar (Claude keeps running in its session);
    the keys go back to ccc."""
    current = find()
    if current is not None:
        _tmux("kill-pane", "-t", current[0])
    bar = find_bar()
    if bar is not None:
        _tmux("kill-pane", "-t", bar)
    if current is not None or bar is not None:
        strip = find_strip()
        if strip is not None:
            _tmux("set-hook", "-w", "-t", _own_pane(), "window-resized",
                  fit_command(_own_pane(), None, strip, sidebar=False))
        else:
            _tmux("set-hook", "-uw", "-t", _own_pane(), "window-resized")
        if _on_ccc_server():
            unbind_keys()
