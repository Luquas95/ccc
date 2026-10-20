import subprocess
from datetime import datetime

import pytest

from ccc.models import PromptRun, RunStatus
from ccc.storage import Storage
from ccc.tui.app import CCContinueApp
from ccc.tui.queue_detail import QueueDetailScreen


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.mark.asyncio
async def test_u_reverts_the_selected_run_and_can_tell_claude(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (("init", "-q"), ("config", "user.email", "t@t"), ("config", "user.name", "t")):
        _git(repo, *args)
    (repo / "a.txt").write_text("one\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    (repo / "a.txt").write_text("two\n")
    _git(repo, "commit", "-qam", "ccc: two")
    db_path = tmp_path / "history.db"
    storage = Storage(db_path)
    queue = storage.create_queue("repo", str(repo), "s1")
    run_id = storage.insert_prompt_run(PromptRun(
        id=0, queue_id=queue.id, queue_item_id=None, prompt_text="write two", started_at=datetime.now(),
        finished_at=datetime.now(), status=RunStatus.SUCCESS, git_commit=_git(repo, "rev-parse", "HEAD")))
    app = CCContinueApp(str(db_path))
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        await app.push_screen(QueueDetailScreen(app.storage, queue.id))
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
        await pilot.press("y")  # revert
        for _ in range(20):
            await pilot.pause(0.05)
            if app.storage.find_run(run_id).reverted_by:
                break
        assert (repo / "a.txt").read_text() == "one\n"
        await pilot.pause()
        await pilot.press("y")  # tell Claude
        await pilot.pause()
        assert "write two" in app.storage.list_pending_items(queue.id)[0].prompt_text
