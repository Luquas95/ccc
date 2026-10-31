"""Claude Code in ccc's own frame (CCC_EMBEDDED_TERMINAL, #133)."""
import pytest

from ccc.orchestrator import start_conversation
from ccc.storage import Storage
from ccc.tui import cli_pane
from ccc.tui.app import CCContinueApp
from ccc.tui.claude_pane import ClaudePane
from ccc.tui.terminal_pane import TerminalPane


@pytest.fixture
def embedded(monkeypatch):
    monkeypatch.setenv("CCC_EMBEDDED_TERMINAL", "1")
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setattr(cli_pane, "attach_command_list", lambda queue_id, keys=None: ["sh", "-c", "cat"])
    monkeypatch.setattr("ccc.clipboard_bridge.start", lambda queue_id, on_copy=None: __import__("threading").Event())


def test_embedded_is_opt_in_and_takes_the_tmux_pane_path_out(monkeypatch):
    monkeypatch.delenv("CCC_EMBEDDED_TERMINAL", raising=False)
    monkeypatch.setenv("TMUX", "/tmp/x,1,0")
    monkeypatch.setenv("TMUX_PANE", "%0")
    assert not cli_pane.embedded() and cli_pane.available()
    monkeypatch.setenv("CCC_EMBEDDED_TERMINAL", "1")
    assert cli_pane.embedded() and not cli_pane.available()


@pytest.mark.asyncio
async def test_enter_opens_claude_in_a_frame_and_the_close_key_closes_it(tmp_path, embedded):
    storage = Storage(str(tmp_path / "h.db"))
    queue = start_conversation(storage, str(tmp_path), set(), name="Demo")
    app = CCContinueApp(str(tmp_path / "h.db"))
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause(0.5)
        await pilot.press("c")
        await pilot.pause(0.5)
        screen = app.screen
        await pilot.press("enter")
        await pilot.pause(0.8)
        pane = screen.claude_pane()
        assert pane is not None and pane.queue_id == queue.id
        assert screen.has_class("-cli-open") and pane.has_keyboard()
        assert "Demo" in str(pane.border_title) and "typing here" in str(pane.border_title)
        # Alt+0 hands the keyboard back to the list, and again to Claude.
        await pilot.press("alt+0")
        await pilot.pause(0.2)
        assert not pane.has_keyboard() and "typing here" not in str(pane.border_title)
        await pilot.press("alt+0")
        await pilot.pause(0.2)
        assert pane.has_keyboard()
        # Keys typed go to the session.
        await pilot.press("h", "i")
        await pilot.pause(0.3)
        assert "hi" in pane.terminal.text()
        await pilot.press("ctrl+right_square_bracket")
        await pilot.pause(0.5)
        assert screen.claude_pane() is None and not screen.has_class("-cli-open")


@pytest.mark.asyncio
async def test_leaving_conversations_closes_the_frame(tmp_path, embedded):
    storage = Storage(str(tmp_path / "h.db"))
    start_conversation(storage, str(tmp_path), set(), name="Demo")
    app = CCContinueApp(str(tmp_path / "h.db"))
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause(0.5)
        await pilot.press("c")
        await pilot.pause(0.5)
        conversations = app.screen
        await pilot.press("enter")
        await pilot.pause(0.8)
        assert conversations.claude_pane() is not None
        await pilot.press("alt+0")  # the keys are Claude's until the keyboard is back in ccc
        await pilot.pause(0.2)
        await pilot.press("d")  # the dashboard
        await pilot.pause(0.5)
        assert conversations.claude_pane() is None
