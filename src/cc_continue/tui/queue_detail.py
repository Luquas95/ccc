from __future__ import annotations

from rich.text import Text
from textual.containers import Container, Horizontal
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Static, TextArea

from cc_continue.launch_options import describe_flags
from cc_continue.models import QueueStatus, RunStatus
from cc_continue.orchestrator import enqueue_prompt
from cc_continue.storage import Storage
from cc_continue.tui.layout import (
    ADD_PROMPT_BUTTON,
    LIVE_SESSIONS_BUTTON,
    MODAL_CSS,
    RETRY_BUTTON,
    SidebarScreen,
    panel,
    styled_status,
)

RUN_STATUS_STYLES = {
    RunStatus.SUCCESS: "green",
    RunStatus.ERROR: "bold red",
    RunStatus.RATE_LIMITED: "yellow",
}


class AddPromptModal(ModalScreen):
    DEFAULT_CSS = MODAL_CSS.format(cls="AddPromptModal")

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, storage: Storage, default_path: str = ""):
        super().__init__()
        self.storage = storage
        self.default_path = default_path

    def compose(self):
        box = Container(
            Static("Project path", classes="modal-label"),
            Input(value=self.default_path, placeholder="/path/to/project", id="add-prompt-path"),
            Static("Prompt", classes="modal-label"),
            TextArea(id="add-prompt-text"),
            Static("", id="add-prompt-error", classes="modal-error"),
            Horizontal(
                Button("Add", id="add-prompt-submit", classes="modal-submit"),
                Button("Cancel", id="add-prompt-cancel", classes="modal-cancel"),
                classes="modal-buttons",
            ),
        )
        box.border_title = "New prompt"
        yield box

    def on_mount(self) -> None:
        # Path is usually prefilled from the selected queue — start in the
        # prompt box then, so you can just type.
        if self.default_path:
            self.query_one("#add-prompt-text", TextArea).focus()

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
                self.query_one("#add-prompt-error", Static).update(Content(str(exc)))
                return
            self.dismiss()
        elif event.button.id == "add-prompt-cancel":
            self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()


class QueueDetailScreen(SidebarScreen):
    """Detail of one queue, opened from the dashboard; shares the
    dashboard's sidebar highlight since it's a drill-down of it."""

    VIEW = "dashboard"
    IS_DETAIL = True
    SUB_TITLE = "Queue detail"

    BINDINGS = [
        ("escape", "back", "Back"),
        ("r", "retry_queue", "Retry blocked"),
    ]

    def __init__(self, storage: Storage, queue_id: int):
        super().__init__(storage)
        self.queue_id = queue_id

    def sidebar_buttons(self):
        return [ADD_PROMPT_BUTTON, LIVE_SESSIONS_BUTTON, RETRY_BUTTON]

    def compose_main(self):
        queue = self.storage.get_queue(self.queue_id)
        yield panel(
            Static(Content.assemble((queue.name, "bold"), "  ", (queue.project_path, "dim")), id="queue-detail-title"),
            Static(id="queue-detail-info"),
            title="Queue",
        )
        yield panel(DataTable(id="queue-history-table"), title="Run history", fill=True)

    def on_mount(self) -> None:
        self._refresh_info()
        table = self.query_one("#queue-history-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Started", "Status", "Tokens", "Result")
        for run in self.storage.runs_for_queue(self.queue_id):
            tokens = run.input_tokens + run.output_tokens + run.cache_read_tokens + run.cache_creation_tokens
            style = RUN_STATUS_STYLES.get(run.status, "")
            status = f"[{style}]{run.status.value}[/]" if style else run.status.value
            table.add_row(
                run.started_at.strftime("%Y-%m-%d %H:%M"),
                status,
                f"{tokens:,}",
                Text((run.result_text or run.error_text or "")[:60].replace("\n", " ")),
            )

    def _refresh_info(self) -> None:
        queue = self.storage.get_queue(self.queue_id)
        # Only the first line is markup (fixed enum/number values); the rest
        # carries arbitrary text (errors, session ids) and stays plain.
        auto = "auto-continue on" if queue.auto_continue else "auto-continue off"
        lines = [
            Content.from_markup(
                f"Status: {styled_status(queue.status)}   ·   Pending: [b]{self.storage.count_pending_items(queue.id)}[/b]"
                f"   ·   Delivery: {queue.delivery_mode.value}"
            ),
            Content(f"Launch: {describe_flags(queue.launch_flags)}  ·  {auto}" + ("  ·  queue paused" if queue.paused else "")),
            Content.assemble(("Session: " + queue.session_id, "dim")),
        ]
        if queue.first_run_flags:
            lines.append(Content.assemble(("First run: " + " ".join(queue.first_run_flags), "yellow")))
        if queue.next_retry_at:
            lines.append(Content.assemble((f"Next retry: {queue.next_retry_at:%Y-%m-%d %H:%M}", "yellow")))
        if queue.last_error:
            lines.append(Content.assemble(("Last error: " + queue.last_error[:200], "red")))
        self.query_one("#queue-detail-info", Static).update(Content("\n").join(lines))

    def default_project_path(self) -> str:
        return self.storage.get_queue(self.queue_id).project_path

    def action_retry_queue(self) -> None:
        queue = self.storage.get_queue(self.queue_id)
        if queue.status in (QueueStatus.BLOCKED_ERROR, QueueStatus.PAUSED_LIMIT):
            self.storage.update_queue_status(queue.id, QueueStatus.IDLE)
            self._refresh_info()
