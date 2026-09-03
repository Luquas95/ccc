from datetime import datetime

import pytest

from cc_continue.models import ItemStatus, PromptRun, QueueStatus, RunStatus
from cc_continue.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "test.db")


def test_create_and_fetch_queue(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    assert q.id is not None
    assert storage.get_queue_by_path("/tmp/demo").id == q.id
    assert storage.get_queue_by_path("/nope") is None


def test_add_item_and_pop_next_pending(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    storage.add_queue_item(q.id, "first")
    storage.add_queue_item(q.id, "second")
    first = storage.next_pending_item(q.id)
    assert first.prompt_text == "first"
    storage.set_item_status(first.id, ItemStatus.DONE)
    second = storage.next_pending_item(q.id)
    assert second.prompt_text == "second"


def test_update_queue_status_persists(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    retry_at = datetime(2026, 9, 3, 15, 30)
    storage.update_queue_status(q.id, QueueStatus.WAITING_RETRY, next_retry_at=retry_at, last_error="boom")
    reloaded = storage.get_queue(q.id)
    assert reloaded.status == QueueStatus.WAITING_RETRY
    assert reloaded.next_retry_at == retry_at
    assert reloaded.last_error == "boom"


def test_reset_running_items_to_pending(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    item = storage.add_queue_item(q.id, "first")
    storage.set_item_status(item.id, ItemStatus.RUNNING)
    storage.update_queue_status(q.id, QueueStatus.RUNNING)
    storage.reset_running_items_to_pending()
    assert storage.next_pending_item(q.id).id == item.id
    assert storage.get_queue(q.id).status == QueueStatus.IDLE


def test_insert_and_list_runs(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    run_id = storage.insert_prompt_run(
        PromptRun(
            id=0,
            queue_id=q.id,
            queue_item_id=None,
            prompt_text="hi",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            status=RunStatus.SUCCESS,
            cost_usd=0.01,
            input_tokens=5,
            output_tokens=5,
        )
    )
    assert run_id > 0
    runs = storage.runs_for_queue(q.id)
    assert len(runs) == 1
    assert runs[0].cost_usd == 0.01


def test_claim_next_pending_item_marks_running_and_returns_it(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    storage.add_queue_item(q.id, "first")
    storage.add_queue_item(q.id, "second")

    claimed = storage.claim_next_pending_item(q.id)
    assert claimed.prompt_text == "first"
    assert claimed.status == ItemStatus.RUNNING

    # peeking with next_pending_item now sees "second", "first" is gone from pending
    assert storage.next_pending_item(q.id).prompt_text == "second"


def test_claim_next_pending_item_is_exclusive_across_storage_instances(storage, tmp_path):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    storage.add_queue_item(q.id, "only item")

    other = Storage(tmp_path / "test.db")  # separate connection, same file

    first_claim = storage.claim_next_pending_item(q.id)
    second_claim = other.claim_next_pending_item(q.id)

    assert first_claim is not None
    assert second_claim is None  # already claimed by `storage`, nothing left to take


def test_claim_next_pending_item_empty_queue_returns_none(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    assert storage.claim_next_pending_item(q.id) is None


def test_count_pending_items(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    assert storage.count_pending_items(q.id) == 0
    storage.add_queue_item(q.id, "a")
    storage.add_queue_item(q.id, "b")
    storage.add_queue_item(q.id, "c")
    assert storage.count_pending_items(q.id) == 3
    claimed = storage.claim_next_pending_item(q.id)
    assert storage.count_pending_items(q.id) == 2
    storage.set_item_status(claimed.id, ItemStatus.DONE)
    assert storage.count_pending_items(q.id) == 2


def test_blocked_seconds_total(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    started = datetime(2026, 9, 3, 10, 0, 0)
    finished = datetime(2026, 9, 3, 10, 5, 0)
    storage.insert_prompt_run(
        PromptRun(
            id=0,
            queue_id=q.id,
            queue_item_id=None,
            prompt_text="hi",
            started_at=started,
            finished_at=finished,
            status=RunStatus.RATE_LIMITED,
        )
    )
    assert storage.blocked_seconds_total() == pytest.approx(300, abs=1)
