import json

import pytest
from textual.app import App
from textual.widgets import DataTable, Input

from ccc.storage import Storage
from ccc.tui.conversations import ConversationsScreen
from ccc.tui.search import SearchModal


def _host(screen):
    class Host(App):
        async def on_mount(self):
            await self.push_screen(screen)

    return Host()


@pytest.fixture
def storage(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", root)
    (root / "-p").mkdir(parents=True)
    storage = Storage(tmp_path / "h.db")
    storage.create_queue("alpha", "/p", "sa")
    storage.create_queue("beta", "/p", "sb")
    for sid, text in (("sa", "nothing here"), ("sb", "the [magic] word")):
        (root / "-p" / f"{sid}.jsonl").write_text(json.dumps(
            {"type": "user", "timestamp": "2026-10-13T10:00:00.000Z", "message": {"role": "user", "content": text}}) + "\n")
    return storage


@pytest.mark.asyncio
async def test_slash_searches_and_enter_opens_conversation(storage):
    alpha = storage.list_queues()[0]
    beta = storage.list_queues()[1]
    app = _host(ConversationsScreen(storage, select_queue_id=alpha.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        app.screen.query_one("#conversation-queue-list").focus()
        await pilot.press("slash")
        await pilot.pause()
        assert isinstance(app.screen, SearchModal)
        app.screen.query_one("#search-input", Input).value = "MAGIC"
        await pilot.press("enter")
        await pilot.pause()
        table = app.screen.query_one("#search-results", DataTable)
        assert table.row_count == 1
        assert "[magic]" in "".join(str(c) for c in table.get_row_at(0))
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ConversationsScreen)
        assert app.screen._current_queue_id == beta.id


@pytest.mark.asyncio
async def test_no_results_message(storage):
    app = _host(SearchModal(storage))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        app.screen.query_one("#search-input", Input).value = "zzz"
        await pilot.press("enter")
        await pilot.pause()
        assert "No matches" in str(app.screen.query_one("#search-status").render())


@pytest.mark.asyncio
async def test_e_exports_current_conversation(storage, tmp_path, monkeypatch):
    monkeypatch.setattr("ccc.tui.conversations.EXPORT_DIR", tmp_path / "exports")
    beta = storage.list_queues()[1]
    app = _host(ConversationsScreen(storage, select_queue_id=beta.id))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        app.screen.query_one("#conversation-queue-list").focus()
        await pilot.press("e")
        await pilot.pause()
    files = list((tmp_path / "exports").glob("beta-*.md"))
    assert len(files) == 1 and "the [magic] word" in files[0].read_text()
