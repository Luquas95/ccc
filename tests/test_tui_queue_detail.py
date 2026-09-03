import pytest

from cc_continue.models import RunStatus
from cc_continue.runner import RunResult
from cc_continue.storage import Storage
from cc_continue.tui.app import CCContinueApp
from cc_continue.tui.queue_detail import QueueDetailScreen


async def fake_run(project_path, session_id, prompt, resume):
    return RunResult(status=RunStatus.SUCCESS, result_text="ok")


@pytest.mark.asyncio
async def test_add_prompt_modal_queues_item(tmp_path):
    db_path = str(tmp_path / "history.db")
    app = CCContinueApp(db_path, run_fn=fake_run)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        path_input = app.screen.query_one("#add-prompt-path")
        text_area = app.screen.query_one("#add-prompt-text")
        path_input.value = "/tmp/proj-b"
        text_area.text = "queued via modal"
        await pilot.click("#add-prompt-submit")
        await pilot.pause()

        queue = app.storage.get_queue_by_path("/tmp/proj-b")
        assert queue is not None

    await app.orchestrator.stop_all()


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
