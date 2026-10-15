import json
from datetime import datetime, timedelta, timezone

from ccc.models import DeliveryMode
from ccc.session_usage import UsageCollector, parse_usage
from ccc.storage import Storage


def _line(msg_id, model="claude-opus-5-5", when=None, tokens=(10, 20, 30, 40), kind="assistant"):
    when = when or datetime.now(timezone.utc)
    return json.dumps({
        "type": kind,
        "timestamp": when.isoformat().replace("+00:00", "Z"),
        "message": {"id": msg_id, "model": model, "usage": {
            "input_tokens": tokens[0], "output_tokens": tokens[1],
            "cache_read_input_tokens": tokens[2], "cache_creation_input_tokens": tokens[3]}},
    }) + "\n"


def test_parse_dedupes_blocks_and_skips_synthetic_and_partial_line(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(_line("m1") + _line("m1") + _line("m2", model="<synthetic>") + '{"type": "user"}\n' + _line("m3")[:20])
    records, offset = parse_usage(f, 0)
    assert [r.message_id for r in records] == ["m1"]
    assert records[0].input_tokens == 10 and records[0].cache_creation_tokens == 40
    # the incomplete last line is read once it's whole
    with f.open("a") as fh:
        fh.write(_line("m3")[20:])
    more, _ = parse_usage(f, offset)
    assert [r.message_id for r in more] == ["m3"]


def _rc_queue(storage, tmp_path, session="sess-rc", delivery=DeliveryMode.REMOTE_CONTROL):
    q = storage.create_queue(f"q-{session}", str(tmp_path), session, delivery_mode=delivery)
    return q


def test_collector_counts_only_rc_queues_since_creation_incl_subagents(tmp_path):
    storage = Storage(tmp_path / "h.db")
    projects = tmp_path / "projects" / "-x"
    projects.mkdir(parents=True)
    rc = _rc_queue(storage, tmp_path)
    headless = _rc_queue(storage, tmp_path, session="sess-h", delivery=DeliveryMode.HEADLESS)
    old = datetime.now(timezone.utc) - timedelta(days=3)
    (projects / "sess-rc.jsonl").write_text(_line("old", when=old) + _line("new1"))
    sub = projects / "sess-rc" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-a.jsonl").write_text(_line("sub1", model="claude-haiku-5-5", tokens=(1, 1, 1, 1)))
    (projects / "sess-h.jsonl").write_text(_line("h1"))

    collector = UsageCollector(projects_root=tmp_path / "projects")
    collector.collect(storage)
    collector.collect(storage)  # idempotent
    assert storage.queue_token_total(rc.id) == 100 + 4
    assert storage.queue_token_total(headless.id) == 0
    assert dict(storage.total_tokens_by_model()) == {"claude-opus-5-5": 100, "claude-haiku-5-5": 4}

    # a fresh collector (daemon restart) re-reads from the start without double counting
    UsageCollector(projects_root=tmp_path / "projects").collect(storage)
    assert storage.queue_token_total(rc.id) == 104


def test_daily_totals_and_delete_include_session_usage(tmp_path):
    storage = Storage(tmp_path / "h.db")
    projects = tmp_path / "projects" / "-x"
    projects.mkdir(parents=True)
    rc = _rc_queue(storage, tmp_path)
    (projects / "sess-rc.jsonl").write_text(_line("m1"))
    UsageCollector(projects_root=tmp_path / "projects").collect(storage)
    today = datetime.now().date().isoformat()
    assert dict(storage.daily_token_totals()) == {today: 100}
    assert storage.queue_token_total(rc.id, day=datetime.now().date()) == 100
    storage.delete_queue(rc.id)
    assert storage.total_tokens_by_model() == [("claude-opus-5-5", 100)]  # history survives
