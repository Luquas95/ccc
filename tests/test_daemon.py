import asyncio
import os
import signal

import pytest

from ccc.daemon import _run
from ccc.models import RunStatus
from ccc.orchestrator import enqueue_prompt
from ccc.runner import RunResult
from ccc.storage import Storage


@pytest.mark.asyncio
async def test_daemon_processes_prequeued_prompt_and_stops_on_sigterm(tmp_path):
    db_path = str(tmp_path / "daemon.db")
    project_dir = tmp_path / "daemon-proj"
    project_dir.mkdir()
    storage = Storage(db_path)
    enqueue_prompt(storage, str(project_dir), "hello")

    calls = []

    async def fake_run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        calls.append(prompt)
        return RunResult(status=RunStatus.SUCCESS, result_text="done")

    async def send_sigterm_once_processed():
        for _ in range(50):
            await asyncio.sleep(0.01)
            if calls:
                break
        os.kill(os.getpid(), signal.SIGTERM)

    await asyncio.wait_for(
        asyncio.gather(_run(db_path, run_fn=fake_run), send_sigterm_once_processed()),
        timeout=5,
    )

    assert calls == ["hello"]
    queue = storage.get_queue_by_path(str(project_dir))
    runs = storage.runs_for_queue(queue.id)
    assert len(runs) == 1
    assert runs[0].status == RunStatus.SUCCESS
