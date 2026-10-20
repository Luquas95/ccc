import pytest
from textual.widgets import Button, Input, TextArea

from ccc.models import GoalStatus
from ccc.storage import Storage
from ccc.tui.app import CCContinueApp
from ccc.tui.goal import GoalModal


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")


@pytest.mark.asyncio
async def test_g_sets_a_goal_and_stop_ends_it(tmp_path):
    db_path = tmp_path / "history.db"
    queue = Storage(db_path).create_queue("shop", str(tmp_path), "s1")
    app = CCContinueApp(str(db_path))
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.screen.set_focus(None)
        await pilot.press("g")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, GoalModal) and modal.queue_id == queue.id
        modal.query_one("#goal-text", TextArea).text = "Expired tokens are rejected, with a test"
        modal.query_one("#goal-check", Input).value = "pytest -q"
        modal.query_one("#goal-rounds", Input).value = "4"
        await pilot.press("ctrl+s")
        await pilot.pause()
        [goal] = app.storage.list_goals(queue.id)
        assert (goal.goal, goal.check_command, goal.max_rounds, goal.status) == \
            ("Expired tokens are rejected, with a test", "pytest -q", 4, GoalStatus.RUNNING)
        assert app.storage.list_pending_items(queue.id)[0].id == goal.item_id
        assert modal.query_one("#goal-start", Button).disabled
        await pilot.click("#goal-stop")
        await pilot.pause()
        assert app.storage.get_goal(goal.id).status == GoalStatus.STOPPED
