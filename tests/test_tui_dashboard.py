import pytest

from cc_continue.cli import add_command
from cc_continue.tui.app import CCContinueApp


@pytest.mark.asyncio
async def test_dashboard_lists_queues(tmp_path):
    db_path = str(tmp_path / "history.db")
    project_dir = tmp_path / "proj-a"
    project_dir.mkdir()
    add_command(db_path, str(project_dir), "do a thing")

    app = CCContinueApp(db_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#dashboard-table")
        rendered_rows = [str(cell) for row_key in table.rows for cell in table.get_row(row_key)]
        assert any("proj-a" in cell for cell in rendered_rows)
        assert any("1" in cell for cell in rendered_rows)  # pending count


@pytest.mark.asyncio
async def test_pressing_enter_opens_queue_detail(tmp_path):
    # DataTable owns the "enter" key itself (select_cursor) — this locks in
    # that opening the detail screen listens for its RowSelected message
    # rather than a screen-level "enter" binding, which never fires.
    db_path = str(tmp_path / "history.db")
    project_dir = tmp_path / "proj-a"
    project_dir.mkdir()
    add_command(db_path, str(project_dir), "do a thing")

    app = CCContinueApp(db_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#dashboard-table")
        table.move_cursor(row=0)
        await pilot.press("enter")
        await pilot.pause()

        from cc_continue.tui.queue_detail import QueueDetailScreen

        assert isinstance(app.screen, QueueDetailScreen)


@pytest.mark.asyncio
async def test_pressing_c_opens_conversations_screen(tmp_path):
    db_path = str(tmp_path / "history.db")
    project_dir = tmp_path / "proj-a"
    project_dir.mkdir()
    add_command(db_path, str(project_dir), "do a thing")

    app = CCContinueApp(db_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()

        from cc_continue.tui.conversations import ConversationsScreen

        assert isinstance(app.screen, ConversationsScreen)
