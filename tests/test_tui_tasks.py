import pytest
from textual.app import App
from textual.widgets import DataTable, TextArea

from ccc.storage import Storage
from ccc.tui.tasks import TaskEditModal, TasksModal


def _setup(tmp_path, *prompts):
    storage = Storage(tmp_path / "h.db")
    queue = storage.create_queue("a", "/tmp/a", "s1")
    for p in prompts:
        storage.add_queue_item(queue.id, p)
    return storage, queue


def _host(modal):
    class Host(App):
        async def on_mount(self):
            await self.push_screen(modal)

    return Host()


def _pending(storage, queue):
    return [i.prompt_text for i in storage.list_pending_items(queue.id)]


@pytest.mark.asyncio
async def test_lists_pending_tasks_and_state(tmp_path):
    storage, queue = _setup(tmp_path, "one", "two\nsecond line")
    app = _host(TasksModal(storage, queue.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        table = app.screen.query_one("#tasks-table", DataTable)
        assert table.row_count == 2
        cells = [str(c) for r in table.rows for c in table.get_row(r)]
        assert any("two" in c for c in cells) and not any("second line" in c for c in cells)
        state = str(app.screen.query_one("#tasks-state").render())
        assert "Auto-continue: on" in state and "Queue: running" in state


@pytest.mark.asyncio
async def test_add_task_via_editor(tmp_path):
    storage, queue = _setup(tmp_path, "one")
    app = _host(TasksModal(storage, queue.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, TaskEditModal)
        app.screen.query_one("#task-text", TextArea).text = "multi\nline task"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert _pending(storage, queue) == ["one", "multi\nline task"]
        assert app.screen.query_one("#tasks-table", DataTable).row_count == 2


@pytest.mark.asyncio
async def test_edit_cancel_and_save(tmp_path):
    storage, queue = _setup(tmp_path, "one", "two")
    app = _host(TasksModal(storage, queue.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        app.screen.query_one("#tasks-table", DataTable).move_cursor(row=1)
        await pilot.press("e")
        await pilot.pause()
        assert app.screen.query_one("#task-text", TextArea).text == "two"
        app.screen.query_one("#task-text", TextArea).text = "changed"
        await pilot.press("escape")
        await pilot.pause()
        assert _pending(storage, queue) == ["one", "two"]
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#task-text", TextArea).text = "two edited"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert _pending(storage, queue) == ["one", "two edited"]


@pytest.mark.asyncio
async def test_delete_and_move(tmp_path):
    storage, queue = _setup(tmp_path, "one", "two", "three")
    app = _host(TasksModal(storage, queue.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        table = app.screen.query_one("#tasks-table", DataTable)
        table.move_cursor(row=2)
        await pilot.press("ctrl+up")
        await pilot.pause()
        assert _pending(storage, queue) == ["one", "three", "two"]
        assert table.cursor_row == 1  # cursor follows the moved task
        await pilot.press("ctrl+down")
        await pilot.pause()
        assert _pending(storage, queue) == ["one", "two", "three"]
        table.move_cursor(row=0)
        await pilot.press("delete")
        await pilot.pause()
        assert _pending(storage, queue) == ["two", "three"]


@pytest.mark.asyncio
async def test_pause_and_auto_continue_toggles(tmp_path):
    storage, queue = _setup(tmp_path, "one")
    app = _host(TasksModal(storage, queue.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("p")
        await pilot.press("o")
        await pilot.pause()
        q = storage.get_queue(queue.id)
        assert q.paused is True and q.auto_continue is False
        state = str(app.screen.query_one("#tasks-state").render())
        assert "Auto-continue: off" in state and "Queue: paused" in state
        await pilot.press("p")
        await pilot.pause()
        assert storage.get_queue(queue.id).paused is False


@pytest.mark.asyncio
async def test_add_task_with_time_and_when_column(tmp_path):
    from datetime import datetime
    from textual.widgets import Input

    storage, queue = _setup(tmp_path, "one")
    app = _host(TasksModal(storage, queue.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#task-text", TextArea).text = "nightly"
        app.screen.query_one("#task-when", Input).value = "2099-01-02 03:04"
        await pilot.press("ctrl+s")
        await pilot.pause()
        item = storage.list_pending_items(queue.id)[1]
        assert item.prompt_text == "nightly" and item.not_before == datetime(2099, 1, 2, 3, 4)
        cells = [str(c) for c in app.screen.query_one("#tasks-table", DataTable).get_row_at(1)]
        assert "2099-01-02 03:04" in cells


@pytest.mark.asyncio
async def test_invalid_time_keeps_editor_open(tmp_path):
    from textual.widgets import Input

    storage, queue = _setup(tmp_path)
    app = _host(TasksModal(storage, queue.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#task-text", TextArea).text = "x"
        app.screen.query_one("#task-when", Input).value = "someday"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, TaskEditModal)
        assert "HH:MM" in str(app.screen.query_one("#task-error").render())
        assert storage.list_pending_items(queue.id) == []


@pytest.mark.asyncio
async def test_reset_uses_usage_and_edit_can_clear_time(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from textual.widgets import Input
    from ccc.usage_api import ProUsage, WindowUsage

    reset_local = (datetime.now() + timedelta(hours=2)).replace(microsecond=0)
    usage = ProUsage(WindowUsage(50, reset_local.astimezone().astimezone(timezone.utc)), None, [])
    monkeypatch.setattr("ccc.tui.tasks.get_pro_usage", lambda force_refresh=False: usage)
    storage, queue = _setup(tmp_path, "one")
    app = _host(TasksModal(storage, queue.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#task-when", Input).value = "reset"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert storage.list_pending_items(queue.id)[0].not_before == reset_local + timedelta(seconds=30)
        await pilot.press("e")
        await pilot.pause()
        assert app.screen.query_one("#task-when", Input).value != ""
        app.screen.query_one("#task-when", Input).value = ""
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert storage.list_pending_items(queue.id)[0].not_before is None
