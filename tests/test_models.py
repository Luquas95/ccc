from datetime import datetime

from ccc.models import ItemStatus, PromptRun, Queue, QueueItem, QueueStatus, RunStatus


def test_queue_defaults():
    q = Queue(id=1, name="demo", project_path="/tmp/demo", session_id="abc")
    assert q.status == QueueStatus.IDLE
    assert q.next_retry_at is None


def test_queue_item_defaults():
    item = QueueItem(id=1, queue_id=1, prompt_text="hello", position=0)
    assert item.status == ItemStatus.PENDING


def test_prompt_run_status_values():
    run = PromptRun(
        id=1,
        queue_id=1,
        queue_item_id=1,
        prompt_text="hi",
        started_at=datetime(2026, 1, 1, 12, 0, 0),
        finished_at=None,
        status=RunStatus.SUCCESS,
    )
    assert run.status.value == "success"
