from datetime import datetime

import pytest
from textual.app import App
from textual.widgets import ProgressBar

from ccc.models import PromptRun, RunStatus
from ccc.storage import Storage
from ccc.tui.analytics import (
    UNAVAILABLE_TEXT,
    AnalyticsScreen,
    build_model_token_bars,
    build_usage_gauges,
)
from ccc.usage_api import ModelUsage, ProUsage, WindowUsage


@pytest.mark.asyncio
async def test_analytics_shows_totals(tmp_path, monkeypatch):
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)

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
async def test_analytics_shows_pro_usage_gauges(tmp_path, monkeypatch):
    fake_usage = ProUsage(
        five_hour=WindowUsage(30.0, datetime(2026, 9, 3, 23, 29).astimezone()),
        seven_day=WindowUsage(47.0, datetime(2026, 9, 4, 12, 59).astimezone()),
        per_model=[ModelUsage("Opus", 62.0, datetime(2026, 9, 4, 12, 59).astimezone())],
    )
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: fake_usage)

    storage = Storage(tmp_path / "history.db")
    screen = AnalyticsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await screen.refresh_pro_usage()
        bars = app.screen.query(ProgressBar)
        assert len(bars) == 3  # 5-hour, weekly, Opus
        percentages = sorted(round(b.percentage * 100) for b in bars)
        assert percentages == [30, 47, 62]

        labels = [str(s.render()) for s in app.screen.query(".usage-gauge-label")]
        assert any("5-hour" in label for label in labels)
        assert any("Weekly (all models)" in label for label in labels)
        assert any("Opus" in label for label in labels)


@pytest.mark.asyncio
async def test_analytics_pro_usage_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)

    storage = Storage(tmp_path / "history.db")
    screen = AnalyticsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await screen.refresh_pro_usage()
        assert len(app.screen.query(ProgressBar)) == 0
        texts = [str(s.render()) for s in app.screen.query("#pro-usage-gauges Static")]
        assert any(UNAVAILABLE_TEXT in t for t in texts)


@pytest.mark.asyncio
async def test_analytics_shows_model_usage_bars(tmp_path, monkeypatch):
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)

    storage = Storage(tmp_path / "history.db")
    queue = storage.create_queue("proj-e", "/tmp/proj-e", "sess-1")
    run_id = storage.insert_prompt_run(
        PromptRun(
            id=0,
            queue_id=queue.id,
            queue_item_id=None,
            prompt_text="x",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            status=RunStatus.SUCCESS,
        )
    )
    storage.insert_run_model_usage(run_id, "claude-sonnet-5", input_tokens=100, output_tokens=100)
    storage.insert_run_model_usage(run_id, "claude-opus-5", input_tokens=10, output_tokens=10)

    screen = AnalyticsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bars = app.screen.query("#model-usage-gauges ProgressBar")
        assert len(bars) == 2
        percentages = sorted(round(b.percentage * 100) for b in bars)
        assert percentages == [10, 100]  # opus scaled relative to busier sonnet

        labels = [str(s.render()) for s in app.screen.query("#model-usage-gauges .usage-gauge-label")]
        assert any("claude-sonnet-5" in label and "200" in label for label in labels)
        assert any("claude-opus-5" in label and "20" in label for label in labels)


def test_build_model_token_bars_empty():
    assert build_model_token_bars([]) == []


def test_build_model_token_bars_scales_relative_to_busiest():
    bars = build_model_token_bars([("claude-sonnet-5", 200), ("claude-opus-5", 20)])
    assert bars[0].relative_pct == 100.0
    assert bars[1].relative_pct == 10.0


def test_build_usage_gauges_none_returns_empty():
    assert build_usage_gauges(None) == []


def test_build_usage_gauges_with_data():
    usage = ProUsage(
        five_hour=WindowUsage(30.0, datetime(2026, 9, 3, 23, 29).astimezone()),
        seven_day=WindowUsage(47.0, datetime(2026, 9, 4, 12, 59).astimezone()),
        per_model=[ModelUsage("Opus", 62.0, datetime(2026, 9, 4, 12, 59).astimezone())],
    )
    gauges = build_usage_gauges(usage)
    assert [g.label for g in gauges] == ["5-hour", "Weekly (all models)", "Weekly · Opus"]
    assert [g.percentage for g in gauges] == [30.0, 47.0, 62.0]


@pytest.mark.asyncio
async def test_analytics_shows_usage_reserve(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from textual.app import App as _App

    from ccc.tui.analytics import AnalyticsScreen
    from ccc.usage_api import ProUsage, WindowUsage

    usage = ProUsage(WindowUsage(10, datetime.now(timezone.utc) + timedelta(hours=1)), None, [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: usage)
    storage = Storage(tmp_path / "h.db")
    storage.set_setting("usage_reserve", "75")

    class Host(_App):
        async def on_mount(self):
            await self.push_screen(AnalyticsScreen(storage))

    app = Host()
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        await pilot.pause()
        assert "75%" in str(app.screen.query_one("#usage-reserve-note").render())


def test_last_days_series_fills_missing_days_with_zero():
    from datetime import date

    from ccc.tui.analytics import last_days_series

    series = last_days_series([("2026-10-13", 5), ("2026-10-15", 7)], days=4, today=date(2026, 10, 15))
    assert series == [0, 5, 0, 7]


@pytest.mark.asyncio
async def test_remote_control_replies_show_in_analytics_and_dashboard(tmp_path, monkeypatch):
    from datetime import date, datetime

    from textual.widgets import DataTable

    from ccc.models import DeliveryMode
    from ccc.session_usage import UsageRecord
    from ccc.tui.app import CCContinueApp

    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")
    storage = Storage(tmp_path / "history.db")
    q = storage.create_queue("phone-chat", str(tmp_path), "sess-rc", delivery_mode=DeliveryMode.REMOTE_CONTROL)
    storage.insert_session_usage(q.id, [UsageRecord("m1", "claude-opus-5-5", datetime.now(), 1, 2, 3, 4)])
    app = CCContinueApp(str(tmp_path / "history.db"))
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        dash = app.screen.query_one("#dashboard-table", DataTable)
        assert "10" in [str(c) for c in dash.get_row_at(0)]
        await pilot.press("v")
        await pilot.pause()
        table = app.screen.query_one("#analytics-project-table", DataTable)
        assert [str(c) for c in table.get_row_at(0)][:2] == ["phone-chat", "10"]
    assert date.today().isoformat() in dict(storage.daily_token_totals())
