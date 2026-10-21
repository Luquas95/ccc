from datetime import datetime, timedelta

import pytest

from ccc import attention
from ccc.models import PromptRun, QueueStatus, RunStatus
from ccc.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "h.db")


def _finished_run(storage, queue_id):
    now = datetime.now() - timedelta(seconds=5)
    storage.insert_prompt_run(PromptRun(id=0, queue_id=queue_id, queue_item_id=None, prompt_text="p", started_at=now,
                                        finished_at=now, status=RunStatus.SUCCESS))


def test_waiting_lists_what_needs_you_most_urgent_first(storage):
    done = storage.create_queue("docs", "/p/docs", "s1")
    _finished_run(storage, done.id)
    error = storage.create_queue("infra", "/p/infra", "s2")
    storage.update_queue_status(error.id, QueueStatus.BLOCKED_ERROR)
    limit = storage.create_queue("big", "/p/big", "s3")
    storage.update_queue_status(limit.id, QueueStatus.PAUSED_LIMIT)
    approval = storage.create_queue("shop", "/p/shop", "s4")
    storage.create_permission_request(approval.id, "Bash", {"command": "ls"})
    quiet = storage.create_queue("quiet", "/p/quiet", "s5")
    archived = storage.create_queue("old", "/p/old", "s6")
    storage.update_queue_status(archived.id, QueueStatus.BLOCKED_ERROR)
    storage.set_queue_archived(archived.id, True)
    running = storage.create_queue("busy", "/p/busy", "s7")
    _finished_run(storage, running.id)
    storage.update_queue_status(running.id, QueueStatus.RUNNING)  # working on the next task: not "done"

    kinds = [(w.name, w.kind) for w in attention.waiting(storage)]
    names = [name for name, _kind in kinds]
    assert kinds[0] == ("shop", attention.APPROVAL)
    assert ("infra", attention.ERROR) in kinds and ("big", attention.LIMIT) in kinds and ("docs", attention.DONE) in kinds
    assert names.index("infra") < names.index("big") < names.index("docs")
    assert not {"quiet", "old", "busy"} & set(names)
    assert "infra" not in [w.name for w in attention.waiting(storage, exclude=error.id)]
    storage.mark_seen(done.id)
    assert "docs" not in [w.name for w in attention.waiting(storage)]


def test_summary_fits_the_width():
    items = [attention.Waiting(1, "shop-api", attention.APPROVAL), attention.Waiting(2, "infra", attention.ERROR),
             attention.Waiting(3, "docs-site", attention.DONE)]
    full = attention.summary(items, 200)
    assert full == "? shop-api waits for approval · ✖ infra error · ◆ docs-site done"
    cut = attention.summary(items, 56)
    assert cut == "? shop-api waits for approval · ✖ infra error · +1 more"
    assert len(attention.summary(items, 20)) <= 20 and attention.summary(items, 20).endswith("+2 more")
    assert attention.summary([], 80) == ""


@pytest.mark.asyncio
async def test_alt_n_opens_the_most_urgent_conversation(tmp_path, monkeypatch):
    from ccc.tui import cli_pane
    from ccc.tui.app import CCContinueApp
    from ccc.tui.conversations import ConversationsScreen

    monkeypatch.setattr(cli_pane, "available", lambda: False)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")
    (tmp_path / "projects").mkdir()
    app = CCContinueApp(str(tmp_path / "h.db"))
    storage = app.storage
    storage.create_queue("quiet", "/p/quiet", "s1")
    broken = storage.create_queue("infra", "/p/infra", "s2")
    storage.update_queue_status(broken.id, QueueStatus.BLOCKED_ERROR)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("alt+n")
        await pilot.pause()
        assert isinstance(app.screen, ConversationsScreen)
        assert app.screen._current_queue_id == broken.id
        await pilot.press("alt+n")  # it's the one you look at now: nothing else waits
        await pilot.pause()
        assert app.screen._current_queue_id == broken.id


def test_publish_waiting_only_when_it_changes(tmp_path, monkeypatch):
    from ccc.tui import cli_pane
    from ccc.tui.app import CCContinueApp

    published = []
    monkeypatch.setattr(cli_pane, "waiting_room", lambda: 200)
    monkeypatch.setattr(cli_pane, "find", lambda: ("%1", 999))
    monkeypatch.setattr(cli_pane, "available", lambda: True)
    monkeypatch.setattr(cli_pane, "publish_waiting", published.append)
    app = CCContinueApp(str(tmp_path / "h.db"))
    broken = app.storage.create_queue("infra", "/p/infra", "s2")
    app.storage.update_queue_status(broken.id, QueueStatus.BLOCKED_ERROR)
    monkeypatch.setattr(app, "run_worker", lambda work, **kwargs: work())
    app.publish_waiting()
    app.publish_waiting()
    assert published == ["✖ infra error"]
    app.storage.update_queue_status(broken.id, QueueStatus.IDLE)
    app.publish_waiting()
    assert published == ["✖ infra error", ""]
