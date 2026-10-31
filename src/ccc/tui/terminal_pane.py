"""A terminal inside ccc: runs a command in a pseudo-terminal and draws its
screen as a widget, so Claude Code can sit in a frame ccc draws itself
(proof of concept for issue #133 — instead of a tmux pane next to ccc).

The command's output goes through pyte (a terminal emulator); the widget
renders pyte's screen line by line, and sends the keys, pastes and the size
back to the pty. Not done yet: mouse, scrollback, the clipboard (OSC 52),
application cursor keys."""
from __future__ import annotations

import asyncio
import fcntl
import os
import pty
import re
import signal
import struct
import subprocess
import termios

import pyte
from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget

# pyte names → Rich's; pyte calls yellow "brown" and writes bright ones "brightred".
_NAMES = {"brown": "yellow"}
# Textual key names → what a terminal sends.
_KEYS = {
    "enter": "\r", "tab": "\t", "escape": "\x1b", "backspace": "\x7f", "space": " ",
    "shift+tab": "\x1b[Z", "up": "\x1b[A", "down": "\x1b[B", "right": "\x1b[C", "left": "\x1b[D",
    "home": "\x1b[H", "end": "\x1b[F", "pageup": "\x1b[5~", "pagedown": "\x1b[6~",
    "delete": "\x1b[3~", "insert": "\x1b[2~",
    "f1": "\x1bOP", "f2": "\x1bOQ", "f3": "\x1bOR", "f4": "\x1bOS", "f5": "\x1b[15~",
    "f6": "\x1b[17~", "f7": "\x1b[18~", "f8": "\x1b[19~", "f9": "\x1b[20~", "f10": "\x1b[21~",
    "f11": "\x1b[23~", "f12": "\x1b[24~",
    "ctrl+up": "\x1b[1;5A", "ctrl+down": "\x1b[1;5B", "ctrl+right": "\x1b[1;5C", "ctrl+left": "\x1b[1;5D",
    "shift+up": "\x1b[1;2A", "shift+down": "\x1b[1;2B", "shift+right": "\x1b[1;2C", "shift+left": "\x1b[1;2D",
    "alt+enter": "\x1b\r", "shift+enter": "\x1b\r", "alt+backspace": "\x1b\x7f",
}


# CSI with a "private" prefix (> = <): pyte reads CSI > 4;2 m (xterm's modifyOtherKeys)
# as "underline" and CSI > 1 u (the kitty keyboard protocol) as "restore cursor".
_PRIVATE_CSI = re.compile(rb"\x1b\[[>=<][0-9;:]*[ -/]*[@-~]")
_PARTIAL_CSI = re.compile(rb"\x1b(\[[>=<0-9;:?]*[ -/]*)?$")


def color(value: str) -> str | None:
    """pyte's colour (a name, "default" or "rrggbb") as a Rich colour."""
    if value == "default":
        return None
    if len(value) == 6 and all(c in "0123456789abcdef" for c in value):
        return f"#{value}"
    value = _NAMES.get(value, value)
    return "bright_" + value[6:] if value.startswith("bright") else value


def encode_key(key: str, character: str | None) -> str | None:
    """The bytes a terminal sends for a Textual key; None if there are none."""
    if key in _KEYS:
        return _KEYS[key]
    if key.startswith("ctrl+") and len(key) == 6 and key[-1].isalpha():
        return chr(ord(key[-1]) - 96)
    if key == "ctrl+@" or key == "ctrl+space":
        return "\x00"
    if key.startswith("alt+") and len(key) == 5:
        return "\x1b" + key[-1]
    if character and character.isprintable():
        return character
    return None


class TerminalPane(Widget, can_focus=True):
    """Runs `command` in a pty and shows it. While focused every key goes
    to the command, except `release_key`, which posts `Released` (the way
    back to ccc)."""

    DEFAULT_CSS = """
    TerminalPane {
        width: 1fr;
        height: 1fr;
    }
    """

    class Released(Message):
        """The release key was pressed."""

    class Exited(Message):
        """The command ended."""

        def __init__(self, returncode: int | None) -> None:
            super().__init__()
            self.returncode = returncode

    def __init__(self, command: list[str], *, release_key: str = "ctrl+right_square_bracket",
                 env: dict[str, str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.command = command
        self.release_key = release_key
        self.env = env
        self.screen_ = pyte.Screen(80, 24)
        self._stream = pyte.ByteStream(self.screen_)
        self._fd: int | None = None
        self._process: subprocess.Popen | None = None
        self._bracketed = False
        self._pending = b""  # the start of an escape sequence cut by a read
        self._dirty = False

    # -- the process --------------------------------------------------

    def start(self) -> None:
        """Start the command at the widget's size (once it has one)."""
        if self._process is not None:
            return
        columns, rows = max(2, self.size.width), max(1, self.size.height)
        master, slave = pty.openpty()
        self._set_size(master, rows, columns)
        env = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", **(self.env or {})}
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        try:
            self._process = subprocess.Popen(
                self.command, stdin=slave, stdout=slave, stderr=slave, env=env,
                start_new_session=True,
                preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0))
        finally:
            os.close(slave)
        self._fd = master
        os.set_blocking(master, False)
        self.screen_.resize(rows, columns)
        self._loop = asyncio.get_running_loop()
        self._loop.add_reader(master, self._readable)

    def stop(self) -> None:
        fd, process = self._fd, self._process
        self._fd = self._process = None
        if fd is not None:
            try:
                self._loop.remove_reader(fd)
            except Exception:  # the loop may be gone already
                pass
            os.close(fd)
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)

    def _readable(self) -> None:
        assert self._fd is not None
        try:
            data = os.read(self._fd, 65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            code = self._process.poll() if self._process else None
            self.stop()
            self.post_message(self.Exited(code))
            return
        data = self._pending + data
        partial = _PARTIAL_CSI.search(data)
        self._pending = data[partial.start():] if partial else b""
        data = _PRIVATE_CSI.sub(b"", data[:partial.start()] if partial else data)
        if b"\x1b[?2004h" in data:
            self._bracketed = True
        if b"\x1b[?2004l" in data:
            self._bracketed = False
        self._stream.feed(data)
        self._request_refresh()

    def _request_refresh(self) -> None:
        # Many reads can arrive within a frame: one repaint is enough.
        if not self._dirty:
            self._dirty = True
            self.set_timer(1 / 60, self._repaint)

    def _repaint(self) -> None:
        self._dirty = False
        self.refresh()

    @staticmethod
    def _set_size(fd: int, rows: int, columns: int) -> None:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))

    def write(self, text: str) -> None:
        """Send text to the command as if typed."""
        if self._fd is not None:
            try:
                os.write(self._fd, text.encode())
            except OSError:
                pass

    # -- the widget ---------------------------------------------------

    def on_mount(self) -> None:
        self.call_after_refresh(self.start)

    def on_unmount(self) -> None:
        self.stop()

    def on_resize(self, event: events.Resize) -> None:
        columns, rows = max(2, event.size.width), max(1, event.size.height)
        if (columns, rows) != (self.screen_.columns, self.screen_.lines):
            self.screen_.resize(rows, columns)
            if self._fd is not None:
                self._set_size(self._fd, rows, columns)
        self.refresh()

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()

    def render_line(self, y: int) -> Strip:
        screen = self.screen_
        width = self.size.width
        if y >= screen.lines:
            return Strip.blank(width)
        line = screen.buffer[y]
        cursor_x = screen.cursor.x if (self.has_focus and not screen.cursor.hidden and y == screen.cursor.y) else -1
        segments: list[Segment] = []
        run, run_style = "", None
        for x in range(min(width, screen.columns)):
            char = line[x]
            fg, bg = color(char.fg), color(char.bg)
            reverse = char.reverse != (x == cursor_x)
            style = Style(color=fg, bgcolor=bg, bold=char.bold or None, italic=char.italics or None,
                          underline=char.underscore or None, strike=char.strikethrough or None,
                          reverse=reverse or None)
            if style != run_style and run:
                segments.append(Segment(run, run_style))
                run = ""
            run_style = style
            run += char.data or " "
        if run:
            segments.append(Segment(run, run_style))
        return Strip(segments).adjust_cell_length(width)

    def text(self) -> str:
        """The screen as plain text (for tests)."""
        return "\n".join(line.rstrip() for line in self.screen_.display)

    # -- input --------------------------------------------------------

    async def _on_key(self, event: events.Key) -> None:
        if event.key == self.release_key:
            event.stop()
            event.prevent_default()
            self.post_message(self.Released())
            return
        data = encode_key(event.key, event.character)
        if data is not None:
            event.stop()
            event.prevent_default()
            self.write(data)

    def on_paste(self, event: events.Paste) -> None:
        event.stop()
        text = event.text
        self.write(f"\x1b[200~{text}\x1b[201~" if self._bracketed else text.replace("\n", "\r"))
