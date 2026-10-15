"""All keyboard shortcuts in one window (? on any screen)."""
from __future__ import annotations

from rich.table import Table
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ccc.tui.layout import MODAL_CSS

# (section, [(binding key, description)]) — keys as Textual names them;
# tests check every screen's bindings are listed here.
KEY_HELP: list[tuple[str, list[tuple[str, str]]]] = [
    ("Everywhere", [
        ("d", "Dashboard"),
        ("c", "Conversations"),
        ("s", "Live sessions"),
        ("v", "Analytics"),
        ("n", "New conversation"),
        ("a", "Add a prompt (path prefilled)"),
        ("question_mark", "This help"),
        ("ctrl+p", "Settings (theme, Telegram, queues, presets, backup)"),
        ("ctrl+t", "Screenshot (SVG into ~/Documents/ccc-screenshots)"),
        ("ctrl+q", "Quit the viewer (queued work keeps running)"),
        ("escape", "Back / close"),
    ]),
    ("Dashboard", [
        ("enter", "Open the queue detail"),
        ("r", "Retry a blocked queue / resume one paused at a limit"),
        ("q", "Quit the viewer (same as Ctrl+Q)"),
    ]),
    ("Conversations", [
        ("r", "Retry / resume the selected conversation"),
        ("t", "Tasks editor (queue, schedule, pause, auto-continue)"),
        ("p", "Approve a tool call Claude is waiting on"),
        ("x", "Archive / restore"),
        ("h", "Show archived conversations"),
        ("ctrl+d", "Delete the conversation (asks first)"),
        ("slash", "Search all conversations"),
        ("e", "Export the conversation as Markdown"),
        ("enter", "Send the message (in the message box)"),
        ("ctrl+j", "New line in the message box (Shift+Enter where supported)"),
    ]),
    ("Tasks editor (t)", [
        ("a", "Add a task"),
        ("e", "Edit the task (also Enter)"),
        ("delete", "Remove the task"),
        ("ctrl+up", "Move up"),
        ("ctrl+down", "Move down"),
        ("p", "Pause / resume the queue"),
        ("o", "Toggle auto-continue"),
        ("ctrl+s", "Save in the task editor"),
    ]),
    ("Approval window (p)", [
        ("y", "Allow"),
        ("a", "Always allow this tool in this conversation"),
        ("n", "Deny"),
    ]),
    ("Queue detail", [
        ("enter", "Show the run's commit diff"),
    ]),
    ("Settings (Ctrl+P)", [
        ("ctrl+s", "Save"),
        ("escape", "Cancel (the theme goes back too)"),
    ]),
]

_PRETTY = {
    "question_mark": "?", "escape": "Esc", "enter": "Enter", "slash": "/", "delete": "Del",
    "ctrl+d": "Ctrl+D", "ctrl+p": "Ctrl+P", "ctrl+t": "Ctrl+T", "ctrl+q": "Ctrl+Q", "ctrl+j": "Ctrl+J", "ctrl+s": "Ctrl+S", "ctrl+up": "Ctrl+↑", "ctrl+down": "Ctrl+↓",
}


def pretty_key(key: str) -> str:
    return _PRETTY.get(key, key)


class KeyHelpModal(ModalScreen):
    DEFAULT_CSS = MODAL_CSS.format(cls="KeyHelpModal") + """
    KeyHelpModal > Container {
        width: 90%;
        max-width: 100;
        height: 90%;
    }
    KeyHelpModal VerticalScroll {
        height: 1fr;
    }
    """

    BINDINGS = [("escape", "close", "Close"), ("question_mark", "close", "Close")]

    def compose(self):
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan", no_wrap=True)
        table.add_column()
        for section, entries in KEY_HELP:
            table.add_row("", "")
            table.add_row(f"[bold green]{section}[/]", "")
            for key, description in entries:
                table.add_row(pretty_key(key), description)
        self.plain_text = "\n".join(
            f"{section}\n" + "\n".join(f"{pretty_key(k)}  {d}" for k, d in entries) for section, entries in KEY_HELP
        )
        box = Container(VerticalScroll(Static(table, id="key-help-text")))
        box.border_title = "Keyboard shortcuts  ·  Esc close"
        yield box

    def action_close(self) -> None:
        self.dismiss()
