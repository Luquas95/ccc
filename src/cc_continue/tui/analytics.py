from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, ProgressBar, Sparkline, Static

from cc_continue.models import RunStatus
from cc_continue.storage import Storage
from cc_continue.usage_api import ProUsage, get_pro_usage

UNAVAILABLE_TEXT = "Claude Pro usage: unavailable (offline, or not logged in via claude.ai OAuth)"


@dataclass
class UsageGauge:
    label: str
    percentage: float  # 0-100
    reset_text: str


def _format_reset(dt: datetime) -> str:
    local_reset = dt.astimezone()
    now = datetime.now().astimezone()
    fmt = "%H:%M" if local_reset.date() == now.date() else "%a %H:%M"
    return local_reset.strftime(fmt)


def build_usage_gauges(usage: ProUsage | None) -> list[UsageGauge]:
    """One gauge per limit window the account actually exposes: always
    5-hour + weekly (combined across models), plus one more per model IF
    the plan populates model-scoped weekly limits (most Pro accounts
    don't — see usage_api.KNOWN_MODEL_KEYS)."""
    if usage is None:
        return []
    gauges = []
    if usage.five_hour:
        gauges.append(UsageGauge("5-hour", usage.five_hour.utilization_pct, _format_reset(usage.five_hour.resets_at)))
    if usage.seven_day:
        gauges.append(UsageGauge("Weekly (all models)", usage.seven_day.utilization_pct, _format_reset(usage.seven_day.resets_at)))
    for m in usage.per_model:
        gauges.append(UsageGauge(f"Weekly · {m.model}", m.utilization_pct, _format_reset(m.resets_at)))
    return gauges


class AnalyticsScreen(Screen):
    BINDINGS = [("escape", "back", "Back")]

    DEFAULT_CSS = """
    AnalyticsScreen #pro-usage-gauges {
        height: auto;
    }
    AnalyticsScreen .usage-gauge-row {
        height: 1;
        margin-bottom: 1;
    }
    AnalyticsScreen .usage-gauge-label {
        width: 42;
    }
    AnalyticsScreen .usage-gauge-row ProgressBar {
        width: 1fr;
    }
    """

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage

    def compose(self):
        yield Header()
        yield Container(
            Static("Claude Pro usage"),
            Container(id="pro-usage-gauges"),
            Static("Tokens per day (last 30 days)"),
            Sparkline([], id="tokens-sparkline"),
            Static("Tokens per project", id="project-tokens-label"),
            DataTable(id="analytics-project-table"),
            Static(id="analytics-summary"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self.refresh_pro_usage(), exclusive=True)
        self.set_interval(30.0, lambda: self.run_worker(self.refresh_pro_usage(), exclusive=True))

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

    async def refresh_pro_usage(self) -> None:
        usage = await asyncio.to_thread(get_pro_usage)
        container = self.query_one("#pro-usage-gauges", Container)
        await container.remove_children()

        gauges = build_usage_gauges(usage)
        if not gauges:
            await container.mount(Static(UNAVAILABLE_TEXT))
            return

        for gauge in gauges:
            bar = ProgressBar(total=100, show_eta=False)
            row = Horizontal(
                Static(f"{gauge.label} (resets {gauge.reset_text})", classes="usage-gauge-label"),
                bar,
                classes="usage-gauge-row",
            )
            await container.mount(row)
            bar.update(progress=gauge.percentage)

    def action_back(self) -> None:
        self.app.pop_screen()
