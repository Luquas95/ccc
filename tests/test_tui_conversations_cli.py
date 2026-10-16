"""Interactive conversations show their Claude Code CLI in a tmux pane
next to ccc (tui.cli_pane is faked here)."""
import pytest
from textual.app import App
from textual.widgets import DataTable

from ccc.models import DeliveryMode
from ccc.storage import Storage
from ccc.tui import cli_pane
from ccc.tui.conversations import ConversationsScreen
from ccc.tui.layout import ConfirmModal


class FakePane:
    def __init__(self):
        self.shown = None  # queue id shown in the pane, None = no pane
        self.focused = 0
        self.closed = 0

    def find(self):
        return ("%1", self.shown) if self.shown is not None else None

    def open(self, queue_id, title=""):
        self.shown = queue_id
        return "%1"

    def close(self):
        if self.shown is not None:
            self.closed += 1
        self.shown = None

    def focus(self):
        self.focused += 1


@pytest.fixture
def pane(monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")
    fake = FakePane()
    monkeypatch.setattr(cli_pane, "available", lambda: True)
    for name in ("find", "open", "close", "focus"):
        monkeypatch.setattr(cli_pane, name, getattr(fake, name))
    return fake


@pytest.fixture
def storage(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.create_queue("cli", str(tmp_path), "s-cli", delivery_mode=DeliveryMode.INTERACTIVE)
    storage.create_queue("headless", str(tmp_path), "s-headless")
    return storage


def _ids(storage):
    return {q.name: q.id for q in storage.list_queues()}


def _host(screen):
    class Host(App):
        async def on_mount(self):
            await self.push_screen(screen)

    return Host()


@pytest.mark.asyncio
async def test_pane_follows_the_selected_conversation(storage, pane):
    ids = _ids(storage)
    app = _host(ConversationsScreen(storage, select_queue_id=ids["cli"]))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        assert pane.shown == ids["cli"]
        assert app.screen.has_class("-cli-open")
        assert pane.focused == 1  # just opened for it: keyboard goes to Claude
        await app.screen._show_queue(ids["headless"])
        assert pane.shown is None and not app.screen.has_class("-cli-open")
        await app.screen._show_queue(ids["cli"])
        assert pane.shown == ids["cli"]
    assert pane.shown is None  # leaving the screen closes it


@pytest.mark.asyncio
async def test_enter_focuses_claude_and_closed_pane_stays_closed(storage, pane):
    ids = _ids(storage)
    app = _host(ConversationsScreen(storage))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await app.screen._show_queue(ids["cli"])
        pane.shown = None  # you pressed Ctrl+] in the pane
        await app.screen._refresh_current()
        assert pane.shown is None and not app.screen.has_class("-cli-open")
        await app.screen._refresh_current()
        assert pane.shown is None  # not reopened behind your back
        table = app.screen.query_one("#conversation-queue-list", DataTable)
        table.focus()
        table.move_cursor(row=app.screen._queue_ids.index(ids["cli"]))
        focused = pane.focused
        await pilot.press("enter")
        await pilot.pause()
        assert pane.shown == ids["cli"] and pane.focused == focused + 1


@pytest.mark.asyncio
async def test_dialog_on_top_gets_the_whole_window(storage, pane):
    ids = _ids(storage)
    app = _host(ConversationsScreen(storage, select_queue_id=ids["cli"]))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        assert pane.shown == ids["cli"]
        app.push_screen(ConfirmModal("t", "x"))
        await pilot.pause()
        assert pane.shown is None
        conversations = next(s for s in app.screen_stack if isinstance(s, ConversationsScreen))
        await conversations._refresh_current()  # the 2-second refresh, under the dialog
        assert pane.shown is None
        await pilot.press("escape")
        await pilot.pause()
        assert pane.shown == ids["cli"]


@pytest.mark.asyncio
async def test_outside_tmux_enter_opens_full_screen(storage, monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(cli_pane, "available", lambda: False)
    opened = []
    monkeypatch.setattr(ConversationsScreen, "_open_cli_full_screen", lambda self, queue_id: opened.append(queue_id))
    ids = _ids(storage)
    app = _host(ConversationsScreen(storage))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        table = app.screen.query_one("#conversation-queue-list", DataTable)
        table.focus()
        table.move_cursor(row=app.screen._queue_ids.index(ids["cli"]))
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert opened == [ids["cli"]]
        # A headless conversation: Enter goes to the message box as before.
        table.move_cursor(row=app.screen._queue_ids.index(ids["headless"]))
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert opened == [ids["cli"]]
        assert app.focused.id == "message-input"
