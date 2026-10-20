import pytest
from textual.widgets import Button, Input, Select, Static, TextArea

from ccc.models import WorkflowStatus
from ccc.storage import Storage
from ccc.tui.app import CCContinueApp
from ccc.tui.workflow import WorkflowModal


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")


@pytest.mark.asyncio
async def test_w_starts_a_workflow_and_answers_its_gate(tmp_path):
    db_path = tmp_path / "history.db"
    queue = Storage(db_path).create_queue("shop", str(tmp_path), "s1")
    app = CCContinueApp(str(db_path))
    async with app.run_test(size=(150, 50)) as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.screen.set_focus(None)
        await pilot.press("w")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, WorkflowModal) and modal.queue_id == queue.id
        modal.query_one("#workflow-template", Select).value = "full"
        await pilot.pause()
        assert "plan → your approval → build" in str(modal.query_one("#workflow-preview", Static).render())
        modal.query_one("#workflow-task", TextArea).text = "Add a CSV export"
        modal.query_one("#workflow-check", Input).value = "pytest -q"
        await pilot.press("ctrl+s")
        await pilot.pause()
        [run] = app.storage.list_workflow_runs(queue.id)
        assert (run.name, run.task, run.check_command) == ("full", "Add a CSV export", "pytest -q")
        assert modal.query_one("#workflow-approve", Button).disabled  # nothing waits yet
        # The daemon planned it and stopped at the gate:
        app.storage.update_workflow_run(run.id, step=1, status=WorkflowStatus.WAITING, plan="the plan")
        modal._refresh()
        await pilot.pause()
        modal.query_one("#workflow-note", Input).value = "small steps"
        await pilot.click("#workflow-approve")
        await pilot.pause()
        run = app.storage.get_workflow_run(run.id)
        assert run.status == WorkflowStatus.RUNNING and run.step == 2 and "small steps" in run.findings
