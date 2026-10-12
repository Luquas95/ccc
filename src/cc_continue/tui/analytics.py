from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from rich.markup import escape
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import DataTable, ProgressBar, Sparkline, Static

from cc_continue.models import RunStatus
from cc_continue.storage import Storage
from cc_continue.tui.layout import SidebarScreen, panel
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


@dataclass
class ModelTokenBar:
    model: str
    tokens: int
    relative_pct: float  # 0-100, scaled against the busiest model


def build_model_token_bars(totals: list[tuple[str, int]]) -> list[ModelTokenBar]:
    """Bars comparing token volume across models CC-continue has actually
    run — its own recorded history, not an Anthropic account limit (which
    doesn't break down by model on every plan; see build_usage_gauges).
    The busiest model is scaled to 100% so bars stay comparable to each
    other even though there's no fixed ceiling like a usage-limit window."""
    if not totals:
        return []
    max_tokens = max(tokens for _, tokens in totals) or 1
    return [ModelTokenBar(model, tokens, (tokens / max_tokens) * 100) for model, tokens in totals]


class AnalyticsScreen(SidebarScreen):
    VIEW = "analytics"
    SUB_TITLE = "Analytics"

    BINDINGS = [("escape", "back", "Back")]

    DEFAULT_CSS = """
    AnalyticsScreen #analytics-scroll {
        height: 1fr;
    }
    AnalyticsScreen #pro-usage-gauges, AnalyticsScreen #model-usage-gauges {
        height: auto;
    }
    AnalyticsScreen .usage-gauge-row {
        height: 1;
        margin-bottom: 1;
    }
    AnalyticsScreen .usage-gauge-row:last-child {
        margin-bottom: 0;
    }
    AnalyticsScreen .usage-gauge-label {
        width: 42;
    }
    AnalyticsScreen .usage-gauge-row ProgressBar {
        width: 1fr;
    }
    AnalyticsScreen #tokens-sparkline {
        height: 3;
    }
    AnalyticsScreen #analytics-summary {
        margin-top: 1;
    }
    """

    def __init__(self, storage: Storage):
        super().__init__(storage)

    def compose_main(self):
        yield VerticalScroll(
            panel(Container(id="pro-usage-gauges"), title="Claude Pro usage (account limits)"),
            panel(Container(id="model-usage-gauges"), title="Tokens by model (this tool's own history)"),
            panel(Sparkline([], id="tokens-sparkline"), title="Tokens per day (last 30 days)"),
            panel(
                DataTable(id="analytics-project-table"),
                Static(id="analytics-summary"),
                title="Tokens per project",
            ),
            id="analytics-scroll",
        )

    async def on_mount(self) -> None:
        self.run_worker(self.refresh_pro_usage(), exclusive=True)
        self.set_interval(30.0, lambda: self.run_worker(self.refresh_pro_usage(), exclusive=True))

        await self._mount_model_usage_bars()

        daily = self.storage.daily_token_totals()
        sparkline = self.query_one("#tokens-sparkline", Sparkline)
        sparkline.data = [v for _, v in daily] or [0]

        table = self.query_one("#analytics-project-table", DataTable)
        table.cursor_type = "row"
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
            table.add_row(escape(queue.name), f"{total_tokens:,}", str(success), str(errors), str(limited))

        blocked_seconds = self.storage.blocked_seconds_total()
        summary = self.query_one("#analytics-summary", Static)
        summary.update(f"Total time blocked on rate limits: [b]{blocked_seconds / 60:.1f} min[/b]")

    async def refresh_pro_usage(self) -> None:
        usage = await asyncio.to_thread(get_pro_usage)
        container = self.query_one("#pro-usage-gauges", Container)
        await container.remove_children()

        gauges = build_usage_gauges(usage)
        if not gauges:
            await container.mount(Static(UNAVAILABLE_TEXT))
            return

        for gauge in gauges:
            await self._mount_gauge_row(container, gauge.label, gauge.percentage, f"resets {gauge.reset_text}")

    async def _mount_model_usage_bars(self) -> None:
        container = self.query_one("#model-usage-gauges", Container)
        bars = build_model_token_bars(self.storage.total_tokens_by_model())
        if not bars:
            await container.mount(Static("No runs recorded yet."))
            return
        for bar in bars:
            await self._mount_gauge_row(container, bar.model, bar.relative_pct, f"{bar.tokens:,} tokens")

    async def _mount_gauge_row(self, container: Container, label: str, percentage: float, suffix: str) -> None:
        progress_bar = ProgressBar(total=100, show_eta=False)
        row = Horizontal(
            Static(f"{label} ({suffix})", classes="usage-gauge-label"),
            progress_bar,
            classes="usage-gauge-row",
        )
        await container.mount(row)
        progress_bar.update(progress=percentage)
