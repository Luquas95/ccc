from __future__ import annotations

from textual.containers import Container, Horizontal
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Static, TextArea

from cc_continue.orchestrator import attach_to_session
from cc_continue.session_discovery import DiscoveredSession, discover_sessions
from cc_continue.storage import Storage


class SessionPickerScreen(Screen):
    """Lists live Claude Code sessions on this machine (via `claude agents
    --json`) so you can queue a prompt for a *specific* one — including
    when several share the same working directory, which project-path-only
    queues can't distinguish."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        self.sessions: list[DiscoveredSession] = []

    def compose(self):
        yield Header()
        yield Container(
            Static("Live Claude Code sessions on this machine"),
            DataTable(id="session-picker-table"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#session-picker-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Name", "Kind", "Status", "Directory")
        self.refresh_sessions()

    def refresh_sessions(self) -> None:
        self.sessions = discover_sessions()
        table = self.query_one("#session-picker-table", DataTable)
        table.clear()
        for session in self.sessions:
            table.add_row(session.name, session.kind, session.status or "", session.cwd)

    def action_refresh(self) -> None:
        self.refresh_sessions()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # DataTable owns the "enter" key itself (action select_cursor),
        # so listen for its message instead of a screen-level binding.
        if event.cursor_row >= len(self.sessions):
            return
        session = self.sessions[event.cursor_row]
        self.app.push_screen(AttachSessionModal(self.storage, session))

    def action_back(self) -> None:
        self.app.pop_screen()


class AttachSessionModal(ModalScreen):
    def __init__(self, storage: Storage, session: DiscoveredSession):
        super().__init__()
        self.storage = storage
        self.session = session

    def compose(self):
        yield Container(
            Static(f"Send prompt to: {self.session.name}  ({self.session.cwd})"),
            TextArea(id="attach-prompt-text"),
            Static("", id="attach-prompt-error"),
            Horizontal(
                Button("Send", id="attach-prompt-submit", variant="primary"),
                Button("Cancel", id="attach-prompt-cancel"),
            ),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "attach-prompt-submit":
            prompt = self.query_one("#attach-prompt-text", TextArea).text.strip()
            if not prompt:
                self.query_one("#attach-prompt-error", Static).update("Prompt is required.")
                return
            attach_to_session(
                self.storage, self.session.session_id, self.session.cwd, self.session.name, prompt
            )
            self.dismiss()
        elif event.button.id == "attach-prompt-cancel":
            self.dismiss()
