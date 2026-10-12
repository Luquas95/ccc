import pytest
from textual.widgets import Button, Input

from cc_continue.storage import Storage
from cc_continue.tui.analytics import AnalyticsScreen
from cc_continue.tui.app import CCContinueApp
from cc_continue.tui.conversations import ConversationsScreen
from cc_continue.tui.dashboard import DashboardScreen
from cc_continue.tui.layout import SidebarScreen
from cc_continue.tui.queue_detail import AddPromptModal, QueueDetailScreen
from cc_continue.tui.session_picker import SessionPickerScreen


@pytest.fixture(autouse=True)
def _no_external_calls(monkeypatch, tmp_path):
    # Sessions view shells out to `claude agents`, analytics hits the usage
    # API, conversations reads ~/.claude transcripts — keep tests offline.
    monkeypatch.setattr("cc_continue.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("cc_continue.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")


def _app(tmp_path):
    db_path = tmp_path / "history.db"
    storage = Storage(db_path)
    storage.create_queue("proj-a", "/tmp/proj-a", "sess-a")
    return CCContinueApp(str(db_path))


def _views_above_home(app):
    return [type(s) for s in app.screen_stack if isinstance(s, SidebarScreen)]


@pytest.mark.asyncio
async def test_hotkeys_switch_views_without_growing_the_stack(tmp_path):
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)

        for key, expected in [
            ("c", ConversationsScreen),
            ("v", AnalyticsScreen),
            ("s", SessionPickerScreen),
        ]:
            await pilot.press(key)
            await pilot.pause()
            assert isinstance(app.screen, expected)
            # home + exactly one view on top, no matter how many switches
            assert _views_above_home(app) == [DashboardScreen, expected]

        await pilot.press("d")
        await pilot.pause()
        assert _views_above_home(app) == [DashboardScreen]


@pytest.mark.asyncio
async def test_every_view_highlights_its_own_nav_item(tmp_path):
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        for key, view in [("d", "dashboard"), ("c", "conversations"), ("s", "sessions"), ("v", "analytics")]:
            await pilot.press(key)
            await pilot.pause()
            active = [w.id for w in app.screen.query(".nav-item.-active")]
            assert active == [f"nav-{view}"]


@pytest.mark.asyncio
async def test_clicking_nav_item_switches_view(tmp_path):
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#nav-analytics")
        await pilot.pause()
        assert isinstance(app.screen, AnalyticsScreen)


@pytest.mark.asyncio
async def test_escape_returns_to_dashboard_but_never_leaves_it(tmp_path):
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)


@pytest.mark.asyncio
async def test_queue_detail_nav_goes_home(tmp_path):
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, QueueDetailScreen)
        await pilot.press("d")
        await pilot.pause()
        assert _views_above_home(app) == [DashboardScreen]


@pytest.mark.asyncio
async def test_sidebar_buttons_stay_out_of_focus_chain(tmp_path):
    # Otherwise the first button grabs initial focus and Enter on the
    # dashboard opens "Add prompt" instead of the selected queue.
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        buttons = list(app.screen.query("#sidebar Button"))
        assert buttons
        assert not any(b.can_focus for b in buttons)
        assert not isinstance(app.focused, Button)


@pytest.mark.asyncio
async def test_add_prompt_prefills_selected_queue_path(tmp_path):
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AddPromptModal)
        assert app.screen.query_one("#add-prompt-path", Input).value == "/tmp/proj-a"
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)


@pytest.mark.asyncio
async def test_n_opens_new_conversation_and_lands_in_conversations(tmp_path):
    from cc_continue.tui.new_conversation import NewConversationModal
    app = _app(tmp_path)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, NewConversationModal)
        app.screen.query_one("#launch-path").value = str(tmp_path)
        await pilot.click("#launch-start")
        await pilot.pause()
        assert isinstance(app.screen, ConversationsScreen)
        newest = max(q.id for q in app.screen.storage.list_queues())
        assert app.screen._current_queue_id == newest
