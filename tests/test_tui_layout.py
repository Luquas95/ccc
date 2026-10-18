import pytest
from textual.widgets import Button, Input

from ccc.storage import Storage
from ccc.tui.analytics import AnalyticsScreen
from ccc.tui.app import CCContinueApp
from ccc.tui.conversations import ConversationsScreen
from ccc.tui.dashboard import DashboardScreen
from ccc.tui.layout import SidebarScreen
from ccc.tui.queue_detail import AddPromptModal, QueueDetailScreen
from ccc.tui.session_picker import SessionPickerScreen


@pytest.fixture(autouse=True)
def _no_external_calls(monkeypatch, tmp_path):
    # Sessions view shells out to `claude agents`, analytics hits the usage
    # API, conversations reads ~/.claude transcripts — keep tests offline.
    monkeypatch.setattr("ccc.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")


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
        await pilot.press("s")  # the dashboard has no buttons
        await pilot.pause()
        buttons = list(app.screen.query("#sidebar Button"))
        assert buttons
        assert not any(b.can_focus for b in buttons)
        assert not isinstance(app.focused, Button)


@pytest.mark.asyncio
async def test_sidebar_buttons_are_only_the_views_own_actions(tmp_path):
    # Switching views is the nav list's job — no "Live sessions" button,
    # and no "Add prompt" on screens without a selected project.
    app = _app(tmp_path)
    expected = {
        "d": [],  # only an overview
        "s": ["Add prompt (a)", "Reload session list (r)"],
        "v": [],
        "c": ["New conversation (n)", "Retry blocked queue (r)"],
    }
    async with app.run_test() as pilot:
        await pilot.pause()
        for key, labels in expected.items():
            await pilot.press(key)
            await pilot.pause()
            assert [str(b.label) for b in app.screen.query("#sidebar Button")] == labels, key


@pytest.mark.asyncio
async def test_add_prompt_prefills_queue_detail_path(tmp_path):
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, QueueDetailScreen)
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AddPromptModal)
        assert app.screen.query_one("#add-prompt-path", Input).value == "/tmp/proj-a"
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, QueueDetailScreen)


@pytest.mark.asyncio
async def test_a_works_only_in_views_with_add_prompt(tmp_path):
    # Keys belong to the view that uses them: "a" is Live sessions' and
    # queue detail's Add prompt, nothing on the other views.
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        for view, screen_type in (("d", DashboardScreen), ("v", AnalyticsScreen), ("c", ConversationsScreen)):
            await pilot.press(view)
            await pilot.pause()
            if screen_type is ConversationsScreen:
                app.screen.set_focus(None)
            await pilot.press("a")
            await pilot.pause()
            assert isinstance(app.screen, screen_type), view
        await pilot.press("s")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AddPromptModal)


@pytest.mark.asyncio
async def test_n_opens_new_conversation_and_lands_in_conversations(tmp_path):
    from ccc.tui.new_conversation import NewConversationModal
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
