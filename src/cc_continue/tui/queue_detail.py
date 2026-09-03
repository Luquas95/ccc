from __future__ import annotations

from textual.containers import Container, Horizontal
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static, TextArea

from cc_continue.orchestrator import enqueue_prompt
from cc_continue.storage import Storage


class AddPromptModal(ModalScreen):
    def __init__(self, storage: Storage, default_path: str = ""):
        super().__init__()
        self.storage = storage
        self.default_path = default_path

    def compose(self):
        yield Container(
            Static("New prompt"),
            Input(value=self.default_path, placeholder="project path", id="add-prompt-path"),
            TextArea(id="add-prompt-text"),
            Static("", id="add-prompt-error"),
            Horizontal(
                Button("Add", id="add-prompt-submit", variant="primary"),
                Button("Cancel", id="add-prompt-cancel"),
            ),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-prompt-submit":
            path = self.query_one("#add-prompt-path", Input).value.strip()
            prompt = self.query_one("#add-prompt-text", TextArea).text.strip()
            if not path or not prompt:
                self.query_one("#add-prompt-error", Static).update("Both path and prompt are required.")
                return
            try:
                enqueue_prompt(self.storage, path, prompt)
            except ValueError as exc:
                self.query_one("#add-prompt-error", Static).update(str(exc))
                return
            self.dismiss()
        elif event.button.id == "add-prompt-cancel":
            self.dismiss()


class QueueDetailScreen(Screen):
    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, storage: Storage, queue_id: int):
        super().__init__()
        self.storage = storage
        self.queue_id = queue_id

    def compose(self):
        queue = self.storage.get_queue(self.queue_id)
        yield Header()
        yield Static(f"Queue: {queue.name} ({queue.project_path})", id="queue-detail-title")
        yield Container(DataTable(id="queue-history-table"))
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#queue-history-table", DataTable)
        table.add_columns("Started", "Status", "Tokens", "Result")
        for run in self.storage.runs_for_queue(self.queue_id):
            tokens = run.input_tokens + run.output_tokens + run.cache_read_tokens + run.cache_creation_tokens
            table.add_row(
                run.started_at.strftime("%Y-%m-%d %H:%M"),
                run.status.value,
                f"{tokens:,}",
                (run.result_text or run.error_text or "")[:60],
            )

    def action_back(self) -> None:
        self.app.pop_screen()
