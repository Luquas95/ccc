from __future__ import annotations

from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Sparkline, Static

from cc_continue.models import RunStatus
from cc_continue.storage import Storage


class AnalyticsScreen(Screen):
    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage

    def compose(self):
        yield Header()
        yield Container(
            Static("Tokens per day (last 30 days)"),
            Sparkline([], id="tokens-sparkline"),
            Static("Tokens per project", id="project-tokens-label"),
            DataTable(id="analytics-project-table"),
            Static(id="analytics-summary"),
        )
        yield Footer()

    def on_mount(self) -> None:
        daily = self.storage.daily_token_totals()
        sparkline = self.query_one("#tokens-sparkline", Sparkline)
        sparkline.data = [v for _, v in daily] or [0]

        table = self.query_one("#analytics-project-table", DataTable)
        table.add_columns("Project", "Total tokens", "Success", "Errors", "Rate-limited")
        for queue in self.storage.list_queues():
            runs = self.storage.runs_for_queue(queue.id)
            total_tokens = sum(
                r.input_tokens + r.output_tokens + r.cache_read_tokens + r.cache_creation_tokens
                for r in runs
            )
            success = sum(1 for r in runs if r.status == RunStatus.SUCCESS)
            errors = sum(1 for r in runs if r.status == RunStatus.ERROR)
            limited = sum(1 for r in runs if r.status == RunStatus.RATE_LIMITED)
            table.add_row(queue.name, f"{total_tokens:,}", str(success), str(errors), str(limited))

        blocked_seconds = self.storage.blocked_seconds_total()
        summary = self.query_one("#analytics-summary", Static)
        summary.update(f"Total time blocked on rate limits: {blocked_seconds / 60:.1f} min")

    def action_back(self) -> None:
        self.app.pop_screen()
