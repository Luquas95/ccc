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
        ("h", "Archive (archived conversations)"),
        ("s", "Live sessions"),
        ("v", "Analytics"),
        ("n", "New conversation"),
        ("question_mark", "This help"),
        ("ctrl+p", "Settings (theme, Telegram, queues, presets, backup)"),
        ("ctrl+q", "Close ccc (it keeps running; `ccc` opens it again)"),
        ("escape", "Back / close"),
    ]),
    ("Dashboard", [
        ("enter", "Open the queue detail"),
        ("q", "Close ccc (same as Ctrl+Q)"),
    ]),
    ("Live sessions", [
        ("enter", "Send the selected session a prompt"),
        ("r", "Reload the session list"),
        ("a", "Add a prompt to a project's queue"),
    ]),
    ("Conversations", [
        ("enter", "Open the conversation's Claude Code CLI (in the list) / send the message (in the box)"),
        ("r", "Blocked: run the failed task again / resume one paused at a limit"),
        ("t", "Tasks editor (queue, schedule, pause, auto-continue)"),
        ("p", "Approve a tool call Claude is waiting on"),
        ("x", "Archive (moves it to Archive, h)"),
        ("alt+0", "Switch between ccc and Claude Code (while it's open beside ccc)"),
        ("ctrl+right_square_bracket", "Close Claude Code beside ccc (it keeps running; Enter in the list opens it)"),
        ("slash", "Search all conversations"),
        ("e", "Export the conversation as Markdown"),
        ("ctrl+j", "New line in the message box (Shift+Enter where supported)"),
        ("alt+1", "Preset prompt 1–9 (⏎ sends it, ✎ puts it into the message box; set in Settings)"),
        ("alt+2", "Preset prompt 2"),
        ("alt+3", "Preset prompt 3"),
        ("alt+4", "Preset prompt 4"),
        ("alt+5", "Preset prompt 5"),
        ("alt+6", "Preset prompt 6"),
        ("alt+7", "Preset prompt 7"),
        ("alt+8", "Preset prompt 8"),
        ("alt+9", "Preset prompt 9"),
    ]),
    ("Archive", [
        ("x", "Restore the conversation"),
        ("enter", "Restore it and open it in Conversations"),
        ("delete", "Delete the conversation from ccc (asks first; Claude Code's transcript stays)"),
        ("slash", "Search all conversations"),
        ("e", "Export the conversation as Markdown"),
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
    ("Analytics", [
        ("left", "Previous calendar month"),
        ("right", "Next calendar month"),
    ]),
    ("Queue detail", [
        ("enter", "Show the run's commit diff"),
        ("a", "Add a prompt (this queue's path prefilled)"),
        ("r", "Blocked: run the failed task again / resume one paused at a limit"),
    ]),
    ("Preset prompt editor (Settings → Add / Edit)", [
        ("ctrl+s", "Save"),
        ("escape", "Cancel"),
    ]),
    ("Settings (Ctrl+P)", [
        ("ctrl+s", "Save"),
        ("escape", "Cancel (the theme goes back too)"),
    ]),
]

_PRETTY = {
    "question_mark": "?", "escape": "Esc", "enter": "Enter", "slash": "/", "delete": "Del",
    "ctrl+d": "Ctrl+D", "ctrl+p": "Ctrl+P", "ctrl+t": "Ctrl+T", "ctrl+q": "Ctrl+Q", "left": "←", "right": "→",
    **{f"alt+{n}": f"Alt+{n}" for n in range(1, 10)}, "ctrl+j": "Ctrl+J", "ctrl+s": "Ctrl+S", "ctrl+up": "Ctrl+↑", "ctrl+down": "Ctrl+↓",
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
