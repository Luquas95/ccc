import pytest
from textual.app import App
from textual.widgets import Checkbox, Input, OptionList

from ccc.storage import Storage
from ccc.tui.new_conversation import NewConversationModal


def _host(modal, results):
    class Host(App):
        async def on_mount(self):
            await self.push_screen(modal, results.append)
    return Host()


@pytest.mark.asyncio
async def test_start_creates_queue_with_ticked_flags(tmp_path):
    storage = Storage(tmp_path / "h.db")
    project = tmp_path / "proj"; project.mkdir()
    results = []
    app = _host(NewConversationModal(storage, browse_root=tmp_path), results)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one("#launch-path", Input).value = str(project)
        app.screen.query_one("#opt-model_haiku", Checkbox).value = True
        await pilot.pause()
        await pilot.click("#launch-start")
        await pilot.pause()
    queue = storage.get_queue(results[0])
    assert queue.project_path == str(project)
    assert queue.launch_flags == ["--dangerously-skip-permissions", "--model", "haiku"]


@pytest.mark.asyncio
async def test_exclusive_checkboxes_untick_each_other(tmp_path):
    app = _host(NewConversationModal(Storage(tmp_path / "h.db"), browse_root=tmp_path), [])
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one("#opt-model_opus", Checkbox).value = True
        await pilot.pause()
        app.screen.query_one("#opt-model_sonnet", Checkbox).value = True
        await pilot.pause()
        assert app.screen.query_one("#opt-model_opus", Checkbox).value is False
        assert app.screen.query_one("#opt-fork", Checkbox).disabled


@pytest.mark.asyncio
async def test_bad_path_shows_error_and_creates_nothing(tmp_path):
    storage = Storage(tmp_path / "h.db")
    results = []
    app = _host(NewConversationModal(storage, browse_root=tmp_path), results)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one("#launch-path", Input).value = str(tmp_path / "missing")
        await pilot.click("#launch-start")
        await pilot.pause()
        assert "not an existing directory" in str(app.screen.query_one("#launch-error").render())
    assert results == [] and storage.list_queues() == []


@pytest.mark.asyncio
async def test_recent_directory_fills_path(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.create_queue("a", str(tmp_path), "s1")
    app = _host(NewConversationModal(storage, browse_root=tmp_path), [])
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        recent = app.screen.query_one("#recent-dirs", OptionList)
        recent.highlighted = 0
        recent.action_select()
        await pilot.pause()
        assert app.screen.query_one("#launch-path", Input).value == str(tmp_path)


@pytest.mark.asyncio
async def test_resume_lists_sessions_of_path(tmp_path, monkeypatch):
    from datetime import datetime
    from ccc.transcript import SessionSummary
    monkeypatch.setattr("ccc.tui.new_conversation.list_sessions_for_directory",
                        lambda p: [SessionSummary("sid-1", datetime(2026, 10, 1, 9, 0), "fix the bug", 4)])
    storage = Storage(tmp_path / "h.db")
    results = []
    app = _host(NewConversationModal(storage, browse_root=tmp_path), results)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one("#launch-path", Input).value = str(tmp_path)
        app.screen.query_one("#opt-session_resume", Checkbox).value = True
        await pilot.pause()
        sessions = app.screen.query_one("#resume-sessions", OptionList)
        assert sessions.display and sessions.option_count == 1
        sessions.highlighted = 0
        await pilot.click("#launch-start")
        await pilot.pause()
    assert storage.get_queue(results[0]).session_id == "sid-1"


@pytest.mark.asyncio
async def test_auto_continue_checkbox(tmp_path):
    storage = Storage(tmp_path / "h.db")
    results = []
    app = _host(NewConversationModal(storage, browse_root=tmp_path), results)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        box = app.screen.query_one("#auto-continue", Checkbox)
        assert box.value is True
        box.value = False
        app.screen.query_one("#launch-path", Input).value = str(tmp_path)
        await pilot.pause()
        await pilot.click("#launch-start")
        await pilot.pause()
    assert storage.get_queue(results[0]).auto_continue is False


@pytest.mark.asyncio
async def test_remote_control_checkbox_default_on(tmp_path):
    from ccc.models import DeliveryMode

    storage = Storage(tmp_path / "h.db")
    results = []
    app = _host(NewConversationModal(storage, browse_root=tmp_path), results)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        assert app.screen.query_one("#remote-control", Checkbox).value is True
        app.screen.query_one("#launch-path", Input).value = str(tmp_path)
        await pilot.click("#launch-start")
        await pilot.pause()
    assert storage.get_queue(results[0]).delivery_mode == DeliveryMode.REMOTE_CONTROL


@pytest.mark.asyncio
async def test_remote_control_unticked_gives_headless(tmp_path):
    from ccc.models import DeliveryMode

    storage = Storage(tmp_path / "h.db")
    results = []
    app = _host(NewConversationModal(storage, browse_root=tmp_path), results)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one("#remote-control", Checkbox).value = False
        app.screen.query_one("#launch-path", Input).value = str(tmp_path)
        await pilot.pause()
        await pilot.click("#launch-start")
        await pilot.pause()
    assert storage.get_queue(results[0]).delivery_mode == DeliveryMode.HEADLESS
