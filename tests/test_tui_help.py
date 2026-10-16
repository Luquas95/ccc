import pytest
from textual.app import App

from ccc.storage import Storage
from ccc.tui.conversations import ConversationsScreen
from ccc.tui.prompt_presets import ALT_DIGIT_CHARS
from ccc.tui.dashboard import DashboardScreen
from ccc.tui.help import KEY_HELP, KeyHelpModal
from ccc.tui.tasks import TasksModal


def _keys(cls):
    keys = set()
    for klass in cls.__mro__:
        if not klass.__module__.startswith("ccc."):
            continue  # Textual's own built-ins (Tab, Ctrl+C copy, ...)
        for binding in getattr(klass, "BINDINGS", []):
            key = binding[0] if isinstance(binding, tuple) else binding.key
            keys.update(key.split(","))
    return keys


def _documented(section):
    return {k for k, _ in dict(KEY_HELP)[section]}


@pytest.mark.parametrize("section,cls,ignore", [
    ("Everywhere", DashboardScreen, {"r", "q", "enter"}),
    # Alt+digit as it arrives through most terminals — documented as alt+N.
    ("Conversations", ConversationsScreen, {"d", "c", "s", "v", "a", "n", "question_mark", *ALT_DIGIT_CHARS.values()}),
    ("Tasks editor (t)", TasksModal, set()),
])
def test_help_lists_every_binding(section, cls, ignore):
    documented = {k for sec, entries in KEY_HELP for k, _ in entries} if section == "Everywhere" else _documented(section)
    missing = _keys(cls) - documented - ignore - {"escape"}
    assert not missing, f"{section}: undocumented keys {missing}"


def _host(screen):
    class Host(App):
        async def on_mount(self):
            await self.push_screen(screen)

    return Host()


@pytest.mark.asyncio
async def test_question_mark_opens_and_closes_help(tmp_path):
    app = _host(DashboardScreen(Storage(tmp_path / "h.db")))
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, KeyHelpModal)
        text = app.screen.plain_text
        assert "Conversations" in text and "Ctrl+J" in text
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)
