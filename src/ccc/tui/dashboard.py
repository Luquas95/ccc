from __future__ import annotations

from datetime import date

from rich.text import Text
from textual.binding import Binding
from textual.widgets import DataTable, Static

from ccc.models import QueueStatus
from ccc.storage import Storage
from ccc.tui.layout import (
    ADD_PROMPT_BUTTON,
    LIVE_SESSIONS_BUTTON,
    RETRY_BUTTON,
    SidebarScreen,
    panel,
    queue_label,
    styled_status,
)


PATH_COLUMN_WIDTH = 48


def _shorten_path(path: str) -> str:
    """Keep the informative tail of long paths so the table doesn't need a
    horizontal scrollbar."""
    return path if len(path) <= PATH_COLUMN_WIDTH else "…" + path[-(PATH_COLUMN_WIDTH - 1):]


class DashboardScreen(SidebarScreen):
    VIEW = "dashboard"
    SUB_TITLE = "Dashboard"

    BINDINGS = [
        # Retry has its sidebar button; Ctrl+Q quits everywhere.
        Binding("r", "retry_queue", "Retry blocked", show=False),
        Binding("q", "quit", "Quit", show=False),
    ]

    def __init__(self, storage: Storage):
        super().__init__(storage)

    def sidebar_buttons(self):
        return [ADD_PROMPT_BUTTON, LIVE_SESSIONS_BUTTON, RETRY_BUTTON]

    def compose_main(self):
        yield panel(Static(id="dashboard-overview"), title="Overview")
        yield panel(DataTable(id="dashboard-table"), title="Queues", fill=True)

    def on_mount(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Project", "Status", "Pending", "Today's tokens", "Path")
        self.refresh_table()
        self.set_interval(2.0, self.refresh_table)

    def refresh_table(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        # Keep the cursor where it was across the periodic rebuild.
        cursor_row = table.cursor_row
        table.clear()
        total_pending = total_tokens = blocked = running = 0
        queues = self._visible_queues()
        unseen = self.storage.unseen_queue_ids()
        waiting = self.storage.queues_waiting_for_approval()
        for queue in queues:
            pending = self.storage.count_pending_items(queue.id)
            today_tokens = self.storage.queue_token_total(queue.id, day=date.today())
            total_pending += pending
            total_tokens += today_tokens
            blocked += queue.status == QueueStatus.BLOCKED_ERROR
            running += queue.status == QueueStatus.RUNNING
            table.add_row(
                queue_label(queue, queue.id in unseen, needs_approval=queue.id in waiting),
                styled_status(queue.status),
                str(pending),
                f"{today_tokens:,}",
                Text(_shorten_path(queue.project_path), style="dim"),
            )
        if queues and cursor_row is not None:
            table.move_cursor(row=min(cursor_row, len(queues) - 1))

        blocked_text = f"[bold red]{blocked} blocked[/]" if blocked else "0 blocked"
        running_text = f"[bold green]{running} running[/]" if running else "0 running"
        self.query_one("#dashboard-overview", Static).update(
            f"[b]{len(queues)}[/b] queues  ·  {running_text}  ·  [b]{total_pending}[/b] pending  ·  "
            f"{blocked_text}  ·  [b]{total_tokens:,}[/b] tokens today"
        )

    def _visible_queues(self):
        return [q for q in self.storage.list_queues() if not q.archived]

    def _selected_queue(self):
        table = self.query_one("#dashboard-table", DataTable)
        queues = self._visible_queues()
        if table.cursor_row is None or table.cursor_row >= len(queues):
            return None
        return queues[table.cursor_row]

    def default_project_path(self) -> str:
        queue = self._selected_queue()
        return queue.project_path if queue else ""

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # DataTable owns the "enter" key itself (action select_cursor),
        # so listen for its message instead of a screen-level binding.
        from ccc.tui.queue_detail import QueueDetailScreen

        queues = self._visible_queues()
        if event.cursor_row >= len(queues):
            return
        queue = queues[event.cursor_row]
        self.app.push_screen(QueueDetailScreen(self.storage, queue.id))

    def action_view_conversations(self) -> None:
        self.action_goto("conversations")

    def action_view_analytics(self) -> None:
        self.action_goto("analytics")

    def action_retry_queue(self) -> None:
        queue = self._selected_queue()
        if queue is not None and queue.status in (QueueStatus.BLOCKED_ERROR, QueueStatus.PAUSED_LIMIT):
            # No in-process runtime to notify (the TUI never executes) —
            # flipping the status is enough, the daemon picks it up on its
            # next poll (at most POLL_INTERVAL_SECONDS later).
            self.storage.update_queue_status(queue.id, QueueStatus.IDLE)
            self.refresh_table()

    def action_quit(self) -> None:
        self.app.exit()
