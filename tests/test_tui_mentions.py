import pytest
from textual.app import App

from ccc.storage import Storage
from ccc.tui.conversations import ConversationsScreen
from ccc.tui.mentions import MentionPopup
from ccc.tui.message_box import MessageBox
from ccc.tui.tasks import TaskEditModal


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr("ccc.tui.mentions.INDEX", __import__("ccc.file_mentions", fromlist=["FileIndex"]).FileIndex())
    folder = tmp_path / "proj"
    (folder / "src" / "app").mkdir(parents=True)
    (folder / "src" / "app" / "login.py").write_text("x")
    (folder / "README.md").write_text("x")
    return folder


def _host(screen):
    class Host(App):
        async def on_mount(self):
            await self.push_screen(screen)

    return Host()


async def _settle(app, pilot):
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


def _popup(app):
    found = app.screen.query(MentionPopup)
    return found.first() if found else None


@pytest.mark.asyncio
async def test_at_offers_files_and_enter_inserts_without_sending(tmp_path, project):
    storage = Storage(tmp_path / "h.db")
    queue = storage.create_queue("p", str(project), "s")
    app = _host(ConversationsScreen(storage, select_queue_id=queue.id))
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        box = app.screen.query_one("#message-input", MessageBox)
        assert box.has_focus
        await pilot.press(*"look @log")
        await _settle(app, pilot)
        popup = _popup(app)
        assert popup is not None and popup.display
        assert [str(popup.get_option_at_index(i).prompt) for i in range(popup.option_count)] == ["@src/app/login.py"]
        await pilot.press("enter")
        await pilot.pause()
        assert box.text == "look @src/app/login.py "
        assert not popup.display
        assert storage.list_pending_items(queue.id) == []  # not sent
        await pilot.press("enter")  # now Enter sends
        await pilot.pause()
        assert len(storage.list_pending_items(queue.id)) == 1


@pytest.mark.asyncio
async def test_esc_closes_the_list_and_leaves_the_at(tmp_path, project):
    storage = Storage(tmp_path / "h.db")
    queue = storage.create_queue("p", str(project), "s")
    screen = ConversationsScreen(storage, select_queue_id=queue.id)
    app = _host(screen)
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        backs = []
        screen.action_back = lambda: backs.append(1)
        await pilot.press(*"me@x and @")
        await _settle(app, pilot)
        popup = _popup(app)
        assert popup.display and popup.option_count == 2  # only the @ at a word start
        await pilot.press("escape")
        await pilot.pause()
        assert not popup.display and backs == []  # Esc closed the list, not the view
        await pilot.press("R")
        await _settle(app, pilot)
        assert not popup.display  # dismissed: stays closed for this @
        assert app.screen.query_one("#message-input", MessageBox).text == "me@x and @R"
        await pilot.press("space", "@", "R")
        await _settle(app, pilot)
        assert popup.display  # a new @
        await pilot.press("tab")
        await pilot.pause()
        assert app.screen.query_one("#message-input", MessageBox).text == "me@x and @R @README.md "


@pytest.mark.asyncio
async def test_task_editor_offers_the_conversations_files(tmp_path, project):
    storage = Storage(tmp_path / "h.db")
    queue = storage.create_queue("p", str(project), "s")
    results = []

    class Host(App):
        async def on_mount(self):
            self.push_screen(TaskEditModal(queue=queue), results.append)

    app = Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("@", "r", "e", "a")
        await _settle(app, pilot)
        assert _popup(app).display
        await pilot.press("escape")  # closes the list, not the editor
        await pilot.pause()
        assert isinstance(app.screen, TaskEditModal) and not _popup(app).display
        await pilot.press("backspace", "a")
        await _settle(app, pilot)
        assert not _popup(app).display  # the same @ stays dismissed
        await pilot.press("escape")  # now Esc cancels the editor
        await pilot.pause()
        assert results == [None]
