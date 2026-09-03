import asyncio

import pytest

from cc_continue.models import ItemStatus, QueueStatus, RunStatus
from cc_continue.orchestrator import Orchestrator
from cc_continue.runner import RunResult
from cc_continue.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "test.db")


async def test_add_prompt_runs_and_marks_done(storage):
    calls = []

    async def fake_run(project_path, session_id, prompt, resume):
        calls.append((prompt, resume))
        return RunResult(status=RunStatus.SUCCESS, result_text="done", cost_usd=0.01)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt("/tmp/proj", "first prompt")

    for _ in range(50):
        await asyncio.sleep(0.01)
        queue = storage.get_queue_by_path("/tmp/proj")
        if queue.status == QueueStatus.IDLE and calls:
            break

    await orch.stop_all()

    assert calls == [("first prompt", False)]
    runs = storage.runs_for_queue(storage.get_queue_by_path("/tmp/proj").id)
    assert len(runs) == 1
    assert runs[0].status == RunStatus.SUCCESS


async def test_second_prompt_resumes_session(storage):
    calls = []

    async def fake_run(project_path, session_id, prompt, resume):
        calls.append(resume)
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt("/tmp/proj", "one")

    for _ in range(50):
        await asyncio.sleep(0.01)
        if len(calls) >= 1:
            break

    orch.add_prompt("/tmp/proj", "two")

    for _ in range(50):
        await asyncio.sleep(0.01)
        if len(calls) >= 2:
            break

    await orch.stop_all()

    assert calls == [False, True]


async def test_hard_error_blocks_queue(storage):
    async def fake_run(project_path, session_id, prompt, resume):
        return RunResult(status=RunStatus.ERROR, error_text="tool crashed")

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt("/tmp/proj", "bad prompt")

    for _ in range(50):
        await asyncio.sleep(0.01)
        queue = storage.get_queue_by_path("/tmp/proj")
        if queue.status == QueueStatus.BLOCKED_ERROR:
            break

    await orch.stop_all()

    queue = storage.get_queue_by_path("/tmp/proj")
    assert queue.status == QueueStatus.BLOCKED_ERROR
    assert queue.last_error == "tool crashed"
    run = storage.runs_for_queue(queue.id)[0]
    assert run.status == RunStatus.ERROR


async def test_rate_limited_reschedules_with_short_backoff(storage, monkeypatch):
    monkeypatch.setattr("cc_continue.orchestrator.next_backoff_seconds", lambda prev: 0)
    call_count = {"n": 0}

    async def fake_run(project_path, session_id, prompt, resume):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return RunResult(status=RunStatus.RATE_LIMITED, error_text="usage limit reached")
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()
    orch.add_prompt("/tmp/proj", "retry me")

    for _ in range(100):
        await asyncio.sleep(0.01)
        if call_count["n"] >= 2:
            break

    await orch.stop_all()

    assert call_count["n"] == 2
    runs = storage.runs_for_queue(storage.get_queue_by_path("/tmp/proj").id)
    statuses = sorted(r.status for r in runs)
    assert RunStatus.RATE_LIMITED in statuses
    assert RunStatus.SUCCESS in statuses


async def test_crash_recovery_requeues_running_items(storage):
    queue = storage.create_queue("proj", "/tmp/proj", "sess-1")
    storage.add_queue_item(queue.id, "interrupted prompt")
    item = storage.next_pending_item(queue.id)
    storage.set_item_status(item.id, ItemStatus.RUNNING)
    storage.update_queue_status(queue.id, QueueStatus.RUNNING)

    async def fake_run(project_path, session_id, prompt, resume):
        return RunResult(status=RunStatus.SUCCESS)

    orch = Orchestrator(storage, run_fn=fake_run)
    await orch.start_all()

    for _ in range(50):
        await asyncio.sleep(0.01)
        reloaded = storage.get_queue_by_path("/tmp/proj")
        if reloaded.status == QueueStatus.IDLE:
            break

    await orch.stop_all()

    runs = storage.runs_for_queue(queue.id)
    assert any(r.prompt_text == "interrupted prompt" and r.status == RunStatus.SUCCESS for r in runs)
