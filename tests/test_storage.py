import sqlite3
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


def test_multiple_queues_can_share_a_project_path(storage):
    q1 = storage.create_queue("session-one", "/tmp/shared", "session-aaa")
    q2 = storage.create_queue("session-two", "/tmp/shared", "session-bbb")
    assert q1.id != q2.id
    assert storage.get_queue_by_session_id("session-aaa").id == q1.id
    assert storage.get_queue_by_session_id("session-bbb").id == q2.id
    # get_queue_by_path is only meaningful for the plain single-queue-per-path
    # flow; with two sharing a path it deterministically returns the oldest.
    assert storage.get_queue_by_path("/tmp/shared").id == q1.id


def test_migrates_old_schema_with_unique_project_path(tmp_path):
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE queues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            project_path TEXT NOT NULL UNIQUE,
            session_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'idle',
            next_retry_at TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE queue_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_id INTEGER NOT NULL REFERENCES queues(id),
            prompt_text TEXT NOT NULL,
            position INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            added_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO queues (id, name, project_path, session_id, status, created_at, updated_at) "
        "VALUES (1, 'old-queue', '/tmp/old-path', 'old-session', 'idle', '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO queue_items (id, queue_id, prompt_text, position, status, added_at) "
        "VALUES (1, 1, 'still here', 0, 'pending', '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    storage = Storage(db_path)  # triggers the migration on open

    queue = storage.get_queue_by_session_id("old-session")
    assert queue is not None
    assert queue.id == 1  # id preserved, so queue_items FK still resolves
    assert queue.project_path == "/tmp/old-path"
    item = storage.next_pending_item(queue.id)
    assert item.prompt_text == "still here"

    # a second queue can now share that same old path (the whole point)
    storage.create_queue("new-queue", "/tmp/old-path", "new-session")
    assert storage.get_queue_by_session_id("new-session") is not None


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


def test_total_tokens_by_model(storage):
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
        )
    )
    storage.insert_run_model_usage(run_id, "claude-sonnet-5", input_tokens=10, output_tokens=5, cache_read_tokens=100)
    storage.insert_run_model_usage(run_id, "claude-opus-5", input_tokens=2, output_tokens=1)

    run_id2 = storage.insert_prompt_run(
        PromptRun(
            id=0,
            queue_id=q.id,
            queue_item_id=None,
            prompt_text="hi again",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            status=RunStatus.SUCCESS,
        )
    )
    storage.insert_run_model_usage(run_id2, "claude-sonnet-5", input_tokens=20, output_tokens=10)

    totals = storage.total_tokens_by_model()
    assert totals[0] == ("claude-sonnet-5", 10 + 5 + 100 + 20 + 10)
    assert totals[1] == ("claude-opus-5", 3)


def test_daily_token_totals_sums_all_token_fields(storage):
    q = storage.create_queue("demo", "/tmp/demo", "session-abc")
    storage.insert_prompt_run(
        PromptRun(
            id=0,
            queue_id=q.id,
            queue_item_id=None,
            prompt_text="hi",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            status=RunStatus.SUCCESS,
            input_tokens=2,
            output_tokens=4,
            cache_read_tokens=100,
            cache_creation_tokens=50,
        )
    )
    totals = storage.daily_token_totals()
    assert len(totals) == 1
    day, total = totals[0]
    assert total == 156


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


import sqlite3 as _sqlite3


def test_launch_flags_round_trip(tmp_path):
    storage = Storage(tmp_path / "h.db")
    q = storage.create_queue("a", "/tmp/a", "s1", launch_flags=["--model", "opus"], first_run_flags=["--fork-session"])
    q = storage.get_queue(q.id)
    assert q.launch_flags == ["--model", "opus"]
    assert q.first_run_flags == ["--fork-session"]
    assert storage.create_queue("b", "/tmp/b", "s2").launch_flags is None


def test_migration_adds_launch_columns_to_old_db(tmp_path):
    db = tmp_path / "old.db"
    conn = _sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE queues (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, project_path TEXT NOT NULL, "
        "session_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'idle', next_retry_at TEXT, last_error TEXT, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, always_resume INTEGER NOT NULL DEFAULT 0, "
        "delivery_mode TEXT NOT NULL DEFAULT 'headless')"
    )
    conn.execute("INSERT INTO queues (name, project_path, session_id, created_at, updated_at) VALUES ('x','/x','sx','2026-01-01T00:00:00','2026-01-01T00:00:00')")
    conn.commit(); conn.close()
    q = Storage(db).list_queues()[0]
    assert q.launch_flags is None and q.first_run_flags is None


def test_set_queue_session_adopts_id_and_clears_first_run(tmp_path):
    storage = Storage(tmp_path / "h.db")
    q = storage.create_queue("a", "/tmp/a", "placeholder", first_run_flags=["--fork-session"])
    storage.set_queue_session(q.id, "real-id")
    q = storage.get_queue(q.id)
    assert (q.session_id, q.first_run_flags, q.always_resume) == ("real-id", None, True)


def test_set_queue_session_collision_raises(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.create_queue("a", "/tmp/a", "taken")
    q = storage.create_queue("b", "/tmp/b", "placeholder")
    with pytest.raises(_sqlite3.IntegrityError):
        storage.set_queue_session(q.id, "taken")


def test_recent_project_paths_and_pending_items(tmp_path):
    storage = Storage(tmp_path / "h.db")
    a = storage.create_queue("a", "/tmp/a", "s1")
    storage.create_queue("b", "/tmp/b", "s2")
    storage.create_queue("a2", "/tmp/a", "s3")
    storage.update_queue_status(a.id, QueueStatus.IDLE)  # bumps updated_at
    assert storage.recent_project_paths()[0] == "/tmp/a"
    assert set(storage.recent_project_paths()) == {"/tmp/a", "/tmp/b"}
    storage.add_queue_item(a.id, "one"); storage.add_queue_item(a.id, "two")
    assert [i.prompt_text for i in storage.list_pending_items(a.id)] == ["one", "two"]
