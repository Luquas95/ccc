import pytest
from textual.widgets import Select, TextArea

from ccc.models import AskStatus
from ccc.storage import Storage
from ccc.tui.app import CCContinueApp
from ccc.tui.ask import AskModal


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")


@pytest.mark.asyncio
async def test_k_asks_another_conversation(tmp_path):
    db_path = tmp_path / "history.db"
    storage = Storage(db_path)
    api = storage.create_queue("API", str(tmp_path), "s2")
    client = storage.create_queue("client", str(tmp_path), "s1")
    app = CCContinueApp(str(db_path))
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        app.push_screen(AskModal(app.storage, client.id))
        await pilot.pause()
        modal = app.screen
        modal.query_one("#ask-target", Select).value = api.id
        modal.query_one("#ask-question", TextArea).text = "Which fields does /orders return?"
        await pilot.press("ctrl+s")
        await pilot.pause()
        [found] = app.storage.list_asks(client.id)
        assert (found.to_queue_id, found.status, found.by_agent) == (api.id, AskStatus.ASKED, False)
        assert app.storage.list_pending_items(api.id)
        await pilot.click("#ask-cancel")
        await pilot.pause()
        assert app.storage.get_ask(found.id).status == AskStatus.CANCELLED
