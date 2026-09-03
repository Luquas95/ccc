from __future__ import annotations

from datetime import date

from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header

from cc_continue.models import QueueStatus
from cc_continue.storage import Storage


class DashboardScreen(Screen):
    BINDINGS = [
        ("a", "add_prompt", "Add prompt"),
        ("enter", "open_detail", "Open"),
        ("v", "view_analytics", "Analytics"),
        ("r", "retry_queue", "Retry blocked"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage

    def compose(self):
        yield Header()
        yield Container(DataTable(id="dashboard-table"))
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Project", "Status", "Pending", "Today's tokens")
        self.refresh_table()
        self.set_interval(2.0, self.refresh_table)

    def refresh_table(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        table.clear()
        for queue in self.storage.list_queues():
            pending = self.storage.count_pending_items(queue.id)
            today_tokens = sum(
                r.input_tokens + r.output_tokens + r.cache_read_tokens + r.cache_creation_tokens
                for r in self.storage.runs_for_queue(queue.id)
                if r.started_at.date() == date.today()
            )
            table.add_row(queue.name, queue.status.value, str(pending), f"{today_tokens:,}")

    def action_add_prompt(self) -> None:
        from cc_continue.tui.queue_detail import AddPromptModal

        self.app.push_screen(AddPromptModal(self.storage))

    def action_open_detail(self) -> None:
        from cc_continue.tui.queue_detail import QueueDetailScreen

        table = self.query_one("#dashboard-table", DataTable)
        if table.cursor_row is None:
            return
        queues = self.storage.list_queues()
        if table.cursor_row >= len(queues):
            return
        queue = queues[table.cursor_row]
        self.app.push_screen(QueueDetailScreen(self.storage, queue.id))

    def action_view_analytics(self) -> None:
        from cc_continue.tui.analytics import AnalyticsScreen

        self.app.push_screen(AnalyticsScreen(self.storage))

    def action_retry_queue(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        if table.cursor_row is None:
            return
        queues = self.storage.list_queues()
        if table.cursor_row >= len(queues):
            return
        queue = queues[table.cursor_row]
        if queue.status == QueueStatus.BLOCKED_ERROR:
            # No in-process runtime to notify (the TUI never executes) —
            # flipping the status is enough, the daemon picks it up on its
            # next poll (at most POLL_INTERVAL_SECONDS later).
            self.storage.update_queue_status(queue.id, QueueStatus.IDLE)

    def action_quit(self) -> None:
        self.app.exit()
