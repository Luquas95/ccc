"""The embedded Claude Code pane (CCC_EMBEDDED_TERMINAL): one pane for the selected conversation,
however many events ask for it at once (mounting and removing are asynchronous)."""
import asyncio

import pytest
from textual.app import App
from textual.containers import Vertical

import ccc.tui.conversations as conversations
from ccc.models import DeliveryMode
from ccc.storage import Storage
from ccc.tui import cli_pane


class SlowPane(Vertical):
    """A stand-in for ClaudePane that takes a moment to go away, as the terminal does."""

    def __init__(self, queue_id, name, storage):
        super().__init__()
        self.queue_id = queue_id

    async def on_unmount(self) -> None:
        await asyncio.sleep(0.2)

    def focus_terminal(self): pass
    def has_keyboard(self): return False
    def waiting_room(self): return 0
    def set_waiting(self, text): pass
    async def refresh_presets(self): pass


def _host(screen):
    class Host(App):
        async def on_mount(self):
            await self.push_screen(screen)

    return Host()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(conversations, "ClaudePane", SlowPane)
    monkeypatch.setattr(cli_pane, "embedded", lambda: True)
    storage = Storage(tmp_path / "h.db")
    mode = next(m for m in DeliveryMode if m.managed)
    queues = [storage.create_queue(f"c{i}", f"/tmp/p{i}", f"s{i}", delivery_mode=mode) for i in range(3)]
    return storage, queues


async def _panes(app):
    await asyncio.sleep(0.5)
    return [p.queue_id for p in app.screen.query(SlowPane)]


@pytest.mark.asyncio
async def test_repeated_syncs_open_one_pane(setup):
    storage, queues = setup
    screen = conversations.ConversationsScreen(storage, select_queue_id=queues[0].id)
    app = _host(screen)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        screen._current_queue_id = queues[1].id
        for _ in range(5):  # the events that ask for it, one after another
            screen._sync_embedded_pane()
        assert await _panes(app) == [queues[1].id]


@pytest.mark.asyncio
async def test_switching_quickly_leaves_only_the_last(setup):
    storage, queues = setup
    screen = conversations.ConversationsScreen(storage, select_queue_id=queues[0].id)
    app = _host(screen)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        for queue in (queues[1], queues[2], queues[1], queues[2]):
            screen._current_queue_id = queue.id
            screen._sync_embedded_pane()
            screen._sync_embedded_pane()
        assert await _panes(app) == [queues[2].id]


@pytest.mark.asyncio
async def test_same_conversation_keeps_its_pane_and_closing_removes_it(setup):
    storage, queues = setup
    screen = conversations.ConversationsScreen(storage, select_queue_id=queues[0].id)
    app = _host(screen)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        first = list(app.screen.query(SlowPane))
        assert [p.queue_id for p in first] == [queues[0].id]
        screen._sync_embedded_pane()
        screen._sync_embedded_pane()
        assert list(app.screen.query(SlowPane)) == first  # the same widget, not a new one
        screen._cli_closed_for = queues[0].id  # Ctrl+]
        screen._sync_embedded_pane()
        assert await _panes(app) == []
