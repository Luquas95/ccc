from datetime import date, datetime

from ccc.models import PromptRun, RunStatus
from ccc.session_usage import UsageRecord
from ccc.storage import Storage
from ccc.token_stats import day_stats, month_stats, months


def _run(storage, queue_id, when, tokens, model=None, status=RunStatus.SUCCESS):
    rid = storage.insert_prompt_run(PromptRun(
        id=0, queue_id=queue_id, queue_item_id=None, prompt_text="p", started_at=when, finished_at=when,
        status=status, input_tokens=tokens))
    if model:
        storage.insert_run_model_usage(rid, model, input_tokens=tokens)
    return rid


def _setup(tmp_path):
    s = Storage(tmp_path / "h.db")
    a = s.create_queue("alpha", "/p/a", "sa")
    b = s.create_queue("beta", "/p/b", "sb")
    _run(s, a.id, datetime(2026, 9, 30, 23, 0), 5, "claude-opus-5-5")
    _run(s, a.id, datetime(2026, 10, 1, 9, 0), 10, "claude-opus-5-5")
    _run(s, a.id, datetime(2026, 10, 1, 10, 0), 7)  # no per-model rows -> "unknown"
    _run(s, a.id, datetime(2026, 10, 2, 10, 0), 0, status=RunStatus.ERROR)
    s.insert_session_usage(b.id, [UsageRecord("m1", "claude-haiku-5-5", datetime(2026, 10, 15, 12, 0), 1, 2, 3, 4)])
    return s, a, b


def test_month_stats_combines_runs_and_session_replies(tmp_path):
    s, a, b = _setup(tmp_path)
    oct_ = month_stats(s, 2026, 10)
    assert oct_.total == 27
    assert oct_.by_day == {date(2026, 10, 1): 17, date(2026, 10, 15): 10}
    assert dict(oct_.by_model) == {"claude-opus-5-5": 10, "unknown": 7, "claude-haiku-5-5": 10}
    assert [(c.name, c.tokens, c.success, c.errors) for c in oct_.by_conversation] == [
        ("alpha", 17, 2, 1), ("beta", 10, 0, 0)]
    assert month_stats(s, 2026, 9).total == 5


def test_months_and_day_and_deleted_names(tmp_path):
    s, a, b = _setup(tmp_path)
    assert months(s) == [(2026, 10, 27), (2026, 9, 5)]
    s.delete_queue(b.id)
    d = day_stats(s, date(2026, 10, 15))
    assert d.total == 10
    assert [(c.name, c.deleted) for c in d.by_conversation] == [("beta", True)]
