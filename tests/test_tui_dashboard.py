import pytest

from cc_continue.cli import add_command
from cc_continue.tui.app import CCContinueApp


@pytest.mark.asyncio
async def test_dashboard_lists_queues(tmp_path):
    db_path = str(tmp_path / "history.db")
    add_command(db_path, "/tmp/proj-a", "do a thing")

    app = CCContinueApp(db_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#dashboard-table")
        rendered_rows = [str(cell) for row_key in table.rows for cell in table.get_row(row_key)]
        assert any("proj-a" in cell for cell in rendered_rows)
        assert any("1" in cell for cell in rendered_rows)  # pending count
