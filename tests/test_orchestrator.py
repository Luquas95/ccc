import asyncio

import pytest

from cc_continue.models import ItemStatus, QueueStatus, RunStatus
from cc_continue.orchestrator import Orchestrator, enqueue_prompt
from cc_continue.runner import RunResult
from cc_continue.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "test.db")


@pytest.fixture
def project_dir(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    return str(d)


async def test_add_prompt_runs_and_marks_done(storage, project_dir):
    calls = []

    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        calls.append((prompt, resume))
        return RunResult(status=RunStatus.SUCCESS, result_text="done", cost_usd=0.01)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt(project_dir, "first prompt")

    for _ in range(50):
        await asyncio.sleep(0.01)
        queue = storage.get_queue_by_path(project_dir)
        if queue.status == QueueStatus.IDLE and calls:
            break

    await orch.stop_all()

    assert calls == [("first prompt", False)]
    runs = storage.runs_for_queue(storage.get_queue_by_path(project_dir).id)
    assert len(runs) == 1
    assert runs[0].status == RunStatus.SUCCESS


async def test_persists_per_model_usage(storage, project_dir):
    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        return RunResult(
            status=RunStatus.SUCCESS,
            model_usage={"claude-sonnet-5": {"input_tokens": 2, "output_tokens": 4}},
        )

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt(project_dir, "first prompt")

    for _ in range(50):
        await asyncio.sleep(0.01)
        if storage.total_tokens_by_model():
            break

    await orch.stop_all()

    assert storage.total_tokens_by_model() == [("claude-sonnet-5", 6)]


async def test_second_prompt_resumes_session(storage, project_dir):
    calls = []

    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        calls.append(resume)
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt(project_dir, "one")

    for _ in range(50):
        await asyncio.sleep(0.01)
        if len(calls) >= 1:
            break

    orch.add_prompt(project_dir, "two")

    for _ in range(50):
        await asyncio.sleep(0.01)
        if len(calls) >= 2:
            break

    await orch.stop_all()

    assert calls == [False, True]


async def test_hard_error_blocks_queue(storage, project_dir):
    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        return RunResult(status=RunStatus.ERROR, error_text="tool crashed")

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt(project_dir, "bad prompt")

    for _ in range(50):
        await asyncio.sleep(0.01)
        queue = storage.get_queue_by_path(project_dir)
        if queue.status == QueueStatus.BLOCKED_ERROR:
            break

    await orch.stop_all()

    queue = storage.get_queue_by_path(project_dir)
    assert queue.status == QueueStatus.BLOCKED_ERROR
    assert queue.last_error == "tool crashed"
    run = storage.runs_for_queue(queue.id)[0]
    assert run.status == RunStatus.ERROR


async def test_rate_limited_reschedules_with_short_backoff(storage, project_dir, monkeypatch):
    monkeypatch.setattr("cc_continue.orchestrator.next_backoff_seconds", lambda prev: 0)
    call_count = {"n": 0}

    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return RunResult(status=RunStatus.RATE_LIMITED, error_text="usage limit reached")
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt(project_dir, "retry me")

    for _ in range(100):
        await asyncio.sleep(0.01)
        if call_count["n"] >= 2:
            break

    await orch.stop_all()

    assert call_count["n"] == 2
    runs = storage.runs_for_queue(storage.get_queue_by_path(project_dir).id)
    statuses = sorted(r.status for r in runs)
    assert RunStatus.RATE_LIMITED in statuses
    assert RunStatus.SUCCESS in statuses


async def test_unhandled_exception_is_caught_and_blocks_queue_visibly(storage, project_dir):
    """A run_fn that raises (e.g. a bad cwd raising FileNotFoundError)
    must never leave the queue silently stuck at 'running' forever."""

    async def raising_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        raise FileNotFoundError("[Errno 2] No such file or directory: 'nope'")

    orch = Orchestrator(storage, run_fn=raising_run)
    await orch.start_all()
    orch.add_prompt(project_dir, "boom")

    for _ in range(50):
        await asyncio.sleep(0.01)
        queue = storage.get_queue_by_path(project_dir)
        if queue.status == QueueStatus.BLOCKED_ERROR:
            break

    await orch.stop_all()

    queue = storage.get_queue_by_path(project_dir)
    assert queue.status == QueueStatus.BLOCKED_ERROR
    assert "FileNotFoundError" in queue.last_error
    runs = storage.runs_for_queue(queue.id)
    assert len(runs) == 1
    assert runs[0].status == RunStatus.ERROR
    assert "FileNotFoundError" in runs[0].error_text


async def test_attach_to_session_creates_live_terminal_queue(storage, project_dir):
    """attach_to_session() is for a session found via discovery — it must
    default to live_terminal delivery (typing into that session's own
    tmux pane) rather than the headless resume path, since that's the
    whole point of attaching to something already live."""
    from cc_continue.models import DeliveryMode
    from cc_continue.orchestrator import attach_to_session

    attach_to_session(storage, "live-session-id", project_dir, "dev-75", "ahoj")

    queue = storage.get_queue_by_session_id("live-session-id")
    assert queue.delivery_mode == DeliveryMode.LIVE_TERMINAL
    assert queue.always_resume is True


async def test_live_terminal_item_waits_until_session_ready_then_delivers(storage, project_dir, monkeypatch):
    monkeypatch.setattr("cc_continue.orchestrator.POLL_INTERVAL_SECONDS", 0.02)

    from cc_continue.live_delivery import DeliveryResult
    from cc_continue.orchestrator import attach_to_session
    from cc_continue.session_discovery import DiscoveredSession

    attach_to_session(storage, "live-session-id", project_dir, "dev-75", "ahoj")

    call_count = {"n": 0}

    def fake_discover_sessions():
        call_count["n"] += 1
        # busy on the first two polls, then idle and ready
        status = "busy" if call_count["n"] < 3 else "idle"
        return [DiscoveredSession(session_id="live-session-id", name="dev-75", cwd=project_dir, kind="interactive", status=status)]

    delivered = []

    def fake_deliver(session_id, prompt_text):
        delivered.append((session_id, prompt_text))
        return DeliveryResult(delivered=True)

    monkeypatch.setattr("cc_continue.orchestrator.discover_sessions", fake_discover_sessions)
    monkeypatch.setattr("cc_continue.orchestrator.deliver_to_live_session", fake_deliver)

    orch = Orchestrator(storage)
    await orch.start_all()

    for _ in range(100):
        await asyncio.sleep(0.01)
        if delivered:
            break

    await orch.stop_all()

    assert delivered == [("live-session-id", "ahoj")]
    assert call_count["n"] >= 3  # actually waited through the busy polls

    queue = storage.get_queue_by_session_id("live-session-id")
    assert queue.status == QueueStatus.IDLE
    runs = storage.runs_for_queue(queue.id)
    assert runs[0].status == RunStatus.SUCCESS


async def test_live_terminal_item_fails_when_session_gone(storage, project_dir, monkeypatch):
    from cc_continue.orchestrator import attach_to_session

    attach_to_session(storage, "live-session-id", project_dir, "dev-75", "ahoj")

    monkeypatch.setattr("cc_continue.orchestrator.discover_sessions", lambda: [])

    orch = Orchestrator(storage)
    await orch.start_all()

    for _ in range(50):
        await asyncio.sleep(0.01)
        queue = storage.get_queue_by_session_id("live-session-id")
        if queue.status == QueueStatus.BLOCKED_ERROR:
            break

    await orch.stop_all()

    queue = storage.get_queue_by_session_id("live-session-id")
    assert queue.status == QueueStatus.BLOCKED_ERROR
    assert "no longer running" in queue.last_error


async def test_discovers_queue_created_after_start_all(storage, tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.orchestrator.POLL_INTERVAL_SECONDS", 0.02)
    calls = []

    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        calls.append(prompt)
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()  # no queues exist yet

    # simulate another process (e.g. `cc-continue add`) creating a queue
    # directly via storage, the way enqueue_prompt() does, without going
    # through this orchestrator at all
    late_dir = tmp_path / "late-proj"
    late_dir.mkdir()
    enqueue_prompt(storage, str(late_dir), "discovered later")

    for _ in range(100):
        await asyncio.sleep(0.01)
        if calls:
            break

    await orch.stop_all()

    assert calls == ["discovered later"]


async def test_two_orchestrators_never_double_execute_same_item(tmp_path):
    """Simulates the daemon + a second process (e.g. someone else's
    Orchestrator against the same DB file) racing for the same queue."""
    db_path = tmp_path / "shared.db"
    storage_a = Storage(db_path)
    storage_b = Storage(db_path)
    project_dir = tmp_path / "shared-proj"
    project_dir.mkdir()

    calls_a = []
    calls_b = []

    async def fake_run_a(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        calls_a.append(prompt)
        return RunResult(status=RunStatus.SUCCESS)

    async def fake_run_b(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        calls_b.append(prompt)
        return RunResult(status=RunStatus.SUCCESS)

    queue = storage_a.create_queue("shared-proj", str(project_dir), "sess-1")
    storage_a.add_queue_item(queue.id, "only prompt")

    orch_a = Orchestrator(storage_a, run_fn=fake_run_a)
    orch_b = Orchestrator(storage_b, run_fn=fake_run_b)
    await orch_a.start_all()
    await orch_b.start_all()

    for _ in range(50):
        await asyncio.sleep(0.01)
        if calls_a or calls_b:
            break

    await orch_a.stop_all()
    await orch_b.stop_all()

    assert calls_a + calls_b == ["only prompt"]
    runs = storage_a.runs_for_queue(queue.id)
    assert len(runs) == 1


async def test_crash_recovery_requeues_running_items(storage, project_dir):
    queue = storage.create_queue("proj", project_dir, "sess-1")
    storage.add_queue_item(queue.id, "interrupted prompt")
    item = storage.next_pending_item(queue.id)
    storage.set_item_status(item.id, ItemStatus.RUNNING)
    storage.update_queue_status(queue.id, QueueStatus.RUNNING)

    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()

    for _ in range(50):
        await asyncio.sleep(0.01)
        reloaded = storage.get_queue_by_path(project_dir)
        if reloaded.status == QueueStatus.IDLE:
            break

    await orch.stop_all()

    runs = storage.runs_for_queue(queue.id)
    assert any(r.prompt_text == "interrupted prompt" and r.status == RunStatus.SUCCESS for r in runs)


from cc_continue.launch_options import DEFAULT_SELECTION, FORK, SESSION_CONTINUE, SESSION_FROM_PR, SESSION_RESUME, toggle
from cc_continue.orchestrator import start_conversation


def test_start_new_conversation_creates_fresh_queue_per_launch(storage, project_dir):
    a = start_conversation(storage, str(project_dir), toggle(DEFAULT_SELECTION, "model_haiku", True))
    b = start_conversation(storage, str(project_dir), DEFAULT_SELECTION, name="second")
    assert a.id != b.id and a.session_id != b.session_id
    assert a.launch_flags == ["--dangerously-skip-permissions", "--model", "haiku"]
    assert not a.always_resume and a.first_run_flags is None and b.name == "second"


def test_start_rejects_missing_directory(storage, tmp_path):
    with pytest.raises(ValueError):
        start_conversation(storage, str(tmp_path / "nope"), DEFAULT_SELECTION)


def test_resume_reuses_existing_queue_unless_fork(storage, project_dir):
    sel = toggle(DEFAULT_SELECTION, SESSION_RESUME, True)
    first = start_conversation(storage, str(project_dir), sel, session_id="abc")
    assert first.always_resume and first.session_id == "abc"
    assert start_conversation(storage, str(project_dir), sel, session_id="abc").id == first.id
    fork = start_conversation(storage, str(project_dir), toggle(sel, FORK, True), session_id="abc")
    assert fork.id != first.id and fork.first_run_flags == ["--resume", "abc", "--fork-session"]


def test_continue_picks_latest_session_of_directory(storage, project_dir, monkeypatch):
    from cc_continue.transcript import SessionSummary
    from datetime import datetime
    monkeypatch.setattr("cc_continue.orchestrator.list_sessions_for_directory",
                        lambda path: [SessionSummary("newest", datetime.now(), "hi", 2)])
    q = start_conversation(storage, str(project_dir), toggle(DEFAULT_SELECTION, SESSION_CONTINUE, True))
    assert q.session_id == "newest"
    monkeypatch.setattr("cc_continue.orchestrator.list_sessions_for_directory", lambda path: [])
    with pytest.raises(ValueError):
        start_conversation(storage, str(project_dir), toggle(DEFAULT_SELECTION, SESSION_CONTINUE, True), name="x")


def test_from_pr_needs_value(storage, project_dir):
    sel = toggle(DEFAULT_SELECTION, SESSION_FROM_PR, True)
    with pytest.raises(ValueError):
        start_conversation(storage, str(project_dir), sel, pr="  ")
    q = start_conversation(storage, str(project_dir), sel, pr="42")
    assert q.first_run_flags == ["--from-pr", "42"]


async def test_first_run_adopts_returned_session_id(storage, project_dir):
    q = start_conversation(storage, str(project_dir),
                           toggle(toggle(DEFAULT_SELECTION, SESSION_RESUME, True), FORK, True), session_id="orig")
    storage.add_queue_item(q.id, "hello")
    calls = []

    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        calls.append((session_id, first_run_flags, launch_flags))
        return RunResult(status=RunStatus.SUCCESS, session_id="forked-id")

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    await asyncio.sleep(0.3)
    await orch.stop_all()
    assert calls[0][1] == ["--resume", "orig", "--fork-session"]
    q = storage.get_queue(q.id)
    assert q.session_id == "forked-id" and q.first_run_flags is None and q.always_resume
