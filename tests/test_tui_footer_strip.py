import json

import pytest
from textual.app import App
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from ccc.tui import footer_strip


def test_tmux_keys():
    assert footer_strip.tmux_key("ctrl+q") == "C-q"
    assert footer_strip.tmux_key("question_mark") == "?"
    assert footer_strip.tmux_key("slash") == "/"
    assert footer_strip.tmux_key("t") == "t"
    assert footer_strip.tmux_key("ctrl+down") is None


@pytest.mark.asyncio
async def test_footer_items_are_what_the_footer_shows():
    class S(Screen):
        BINDINGS = [Binding("t", "tasks", "Tasks"), Binding("x", "hidden", "Hidden", show=False)]

        def action_tasks(self):
            pass

        def action_hidden(self):
            pass

    class A(App):
        BINDINGS = [Binding("ctrl+q", "quit", "Close")]

        def on_mount(self):
            self.push_screen(S())

    app = A()
    async with app.run_test() as pilot:
        await pilot.pause()
        items = footer_strip.footer_items(app)
    assert ["t", "Tasks", "t"] in items
    assert any(i[1] == "Close" and i[2] == "C-q" for i in items)
    assert not any(i[1] == "Hidden" for i in items)


def test_decode_ignores_garbage():
    assert footer_strip.decode("not json") == []
    assert footer_strip.decode(json.dumps([["t", "Tasks", "t"], "x"])) == [["t", "Tasks", "t"]]


@pytest.mark.asyncio
async def test_strip_shows_published_keys_and_clicks_press_them(monkeypatch):
    sent = []
    value = footer_strip.encode([["?", "Keys", "?"], ["t", "Tasks", "t"]])

    def tmux(*args):
        sent.append(args)
        import subprocess
        return subprocess.CompletedProcess(args, 0, value if args[0] == "show-options" else "", "")

    monkeypatch.setattr(footer_strip, "_tmux", tmux)
    app = footer_strip.FooterStrip("%0")
    async with app.run_test(size=(100, 1)) as pilot:
        await pilot.pause()
        items = list(app.query(".strip-item"))
        assert [str(i.render()) for i in items] == ["? Keys", "t Tasks"]
        await pilot.click(items[1])
        await pilot.pause()
    assert ("send-keys", "-t", "%0", "t") in sent and ("select-pane", "-t", "%0") in sent
