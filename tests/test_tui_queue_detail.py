import pytest

from cc_continue.storage import Storage
from cc_continue.tui.app import CCContinueApp
from cc_continue.tui.queue_detail import QueueDetailScreen


@pytest.mark.asyncio
async def test_add_prompt_modal_queues_item(tmp_path):
    db_path = str(tmp_path / "history.db")
    project_dir = tmp_path / "proj-b"
    project_dir.mkdir()
    app = CCContinueApp(db_path)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        path_input = app.screen.query_one("#add-prompt-path")
        text_area = app.screen.query_one("#add-prompt-text")
        path_input.value = str(project_dir)
        text_area.text = "queued via modal"
        await pilot.click("#add-prompt-submit")
        await pilot.pause()

        queue = app.storage.get_queue_by_path(str(project_dir))
        assert queue is not None
        item = app.storage.next_pending_item(queue.id)
        assert item.prompt_text == "queued via modal"


@pytest.mark.asyncio
async def test_add_prompt_modal_shows_error_for_missing_directory(tmp_path):
    db_path = str(tmp_path / "history.db")
    app = CCContinueApp(db_path)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        path_input = app.screen.query_one("#add-prompt-path")
        text_area = app.screen.query_one("#add-prompt-text")
        path_input.value = str(tmp_path / "does-not-exist")
        text_area.text = "ahoj"
        await pilot.click("#add-prompt-submit")
        await pilot.pause()

        # modal stays open with an error, nothing got queued
        error = app.screen.query_one("#add-prompt-error")
        assert "not an existing directory" in str(error.render())
        assert app.storage.get_queue_by_path(str(tmp_path / "does-not-exist")) is None


@pytest.mark.asyncio
async def test_queue_detail_shows_history(tmp_path):
    db_path = str(tmp_path / "history.db")
    storage = Storage(db_path)
    queue = storage.create_queue("proj-c", "/tmp/proj-c", "sess-1")

    from textual.app import App as _App

    class _HostApp(_App):
        async def on_mount(self):
            await self.push_screen(QueueDetailScreen(storage, queue.id))

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.screen.query_one("#queue-detail-title")
        assert "proj-c" in str(header.render())
