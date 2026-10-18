import pytest

from ccc.cli import add_command
from ccc.tui.app import CCContinueApp


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

        from ccc.tui.queue_detail import QueueDetailScreen

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

        from ccc.tui.conversations import ConversationsScreen

        assert isinstance(app.screen, ConversationsScreen)


@pytest.mark.asyncio
async def test_retry_button_only_for_a_blocked_queue(tmp_path):
    from ccc.models import QueueStatus
    from ccc.storage import Storage
    from ccc.tui.conversations import ConversationsScreen

    db_path = str(tmp_path / "history.db")
    storage = Storage(db_path)
    ok = storage.create_queue("ok", str(tmp_path), "s-ok")
    stuck = storage.create_queue("stuck", str(tmp_path), "s-stuck")
    storage.update_queue_status(stuck.id, QueueStatus.BLOCKED_ERROR, last_error="boom")

    app = CCContinueApp(db_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        button = app.screen.query_one("#sidebar-retry")
        table = app.screen.query_one("#dashboard-table")
        rows = [q.id for q in storage.list_queues()]
        table.move_cursor(row=rows.index(ok.id))
        await pilot.pause()
        assert not button.display
        table.move_cursor(row=rows.index(stuck.id))
        await pilot.pause()
        assert button.display
        await pilot.press("r")  # retried: nothing left to retry
        await pilot.pause()
        assert not button.display

        storage.update_queue_status(stuck.id, QueueStatus.PAUSED_LIMIT)
        await app.push_screen(ConversationsScreen(storage, select_queue_id=ok.id))
        await pilot.pause()
        assert not app.screen.query_one("#sidebar-retry").display
        app.screen.open_conversation(stuck.id)
        await pilot.pause()
        assert app.screen.query_one("#sidebar-retry").display


@pytest.mark.asyncio
async def test_no_retry_button_without_conversations(tmp_path):
    app = CCContinueApp(str(tmp_path / "history.db"))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.query_one("#sidebar-retry").display
