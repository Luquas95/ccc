from datetime import datetime

import pytest
from textual.app import App

from cc_continue.models import PromptRun, RunStatus
from cc_continue.storage import Storage
from cc_continue.tui.analytics import AnalyticsScreen, format_pro_usage_line
from cc_continue.usage_api import ProUsage, WindowUsage


@pytest.mark.asyncio
async def test_analytics_shows_totals(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.tui.analytics.get_pro_usage", lambda: None)

    db_path = str(tmp_path / "history.db")
    storage = Storage(db_path)
    queue = storage.create_queue("proj-d", "/tmp/proj-d", "sess-1")
    storage.insert_prompt_run(
        PromptRun(
            id=0,
            queue_id=queue.id,
            queue_item_id=None,
            prompt_text="x",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            status=RunStatus.SUCCESS,
            input_tokens=100,
            output_tokens=50,
        )
    )

    screen = AnalyticsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#analytics-project-table")
        rows = [str(cell) for row_key in table.rows for cell in table.get_row(row_key)]
        assert any("proj-d" in cell for cell in rows)
        assert any("150" in cell for cell in rows)


@pytest.mark.asyncio
async def test_analytics_shows_pro_usage_line(tmp_path, monkeypatch):
    fake_usage = ProUsage(
        five_hour=WindowUsage(30.0, datetime(2026, 9, 3, 23, 29).astimezone()),
        seven_day=WindowUsage(47.0, datetime(2026, 9, 4, 12, 59).astimezone()),
    )
    monkeypatch.setattr("cc_continue.tui.analytics.get_pro_usage", lambda: fake_usage)

    storage = Storage(tmp_path / "history.db")
    screen = AnalyticsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await screen.refresh_pro_usage()
        line = str(app.screen.query_one("#pro-usage-line").render())
        assert "30%" in line
        assert "47%" in line


def test_format_pro_usage_line_unavailable():
    assert "unavailable" in format_pro_usage_line(None)


def test_format_pro_usage_line_with_data():
    usage = ProUsage(
        five_hour=WindowUsage(30.0, datetime(2026, 9, 3, 23, 29).astimezone()),
        seven_day=WindowUsage(47.0, datetime(2026, 9, 4, 12, 59).astimezone()),
    )
    line = format_pro_usage_line(usage)
    assert "5-hour: 30% used" in line
    assert "weekly: 47% used" in line
