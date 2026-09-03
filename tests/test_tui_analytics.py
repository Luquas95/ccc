from datetime import datetime

import pytest
from textual.app import App

from cc_continue.models import PromptRun, RunStatus
from cc_continue.storage import Storage
from cc_continue.tui.analytics import AnalyticsScreen


@pytest.mark.asyncio
async def test_analytics_shows_totals(tmp_path):
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

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(AnalyticsScreen(storage))

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#analytics-project-table")
        rows = [str(cell) for row_key in table.rows for cell in table.get_row(row_key)]
        assert any("proj-d" in cell for cell in rows)
        assert any("150" in cell for cell in rows)
