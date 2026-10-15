from datetime import date, datetime

from ccc.models import PromptRun, RunStatus
from ccc.obsidian_export import export
from ccc.session_usage import UsageRecord
from ccc.storage import Storage


def _storage(tmp_path):
    s = Storage(tmp_path / "h.db")
    a = s.create_queue("alpha", "/p/a", "sa")
    b = s.create_queue("beta|pipe", "/p/b", "sb")
    when = datetime(2026, 10, 1, 9, 0)
    rid = s.insert_prompt_run(PromptRun(id=0, queue_id=a.id, queue_item_id=None, prompt_text="p", started_at=when,
                                        finished_at=when, status=RunStatus.SUCCESS, input_tokens=1_500_000))
    s.insert_run_model_usage(rid, "claude-opus-5-5", input_tokens=1_500_000)
    s.insert_session_usage(b.id, [UsageRecord("m1", "claude-haiku-5-5", datetime(2026, 9, 30, 8, 0), 100, 0, 0, 0)])
    return s


def test_export_writes_index_months_and_days(tmp_path):
    s = _storage(tmp_path)
    out = tmp_path / "vault" / "ccc_analytics"
    written = export(s, out, today=date(2026, 10, 15))
    names = sorted(p.name for p in out.iterdir())
    assert names == ["2026-09-30.md", "2026-09.md", "2026-10-01.md", "2026-10.md", "ccc_analytics.md"]
    assert written == 5

    index = (out / "ccc_analytics.md").read_text()
    assert index.startswith("---\ngenerator: ccc\ntokens: 1500100\n")
    assert "[[2026-10\\|October 2026]] | 1 500 000" in index
    assert "[[2026-09\\|September 2026]] | 100" in index
    assert "[[2026-10-01\\|1]]<br>1.5 M" in index  # this month's calendar links the day
    assert "xychart-beta" in index

    month = (out / "2026-10.md").read_text()
    assert "**1 500 000 tokens**" in month and "| alpha | 1 500 000 | 1 | 0 |" in month
    assert "| claude-opus-5-5 | 1 500 000 |" in month
    day = (out / "2026-09-30.md").read_text()
    assert "date: 2026-09-30" in day and "beta\\|pipe" in day and "[[2026-09|September 2026]]" in day


def test_export_is_idempotent_and_leaves_foreign_files_alone(tmp_path):
    s = _storage(tmp_path)
    out = tmp_path / "ccc_analytics"
    out.mkdir()
    (out / "2026-10.md").write_text("# my own note\n")
    export(s, out, today=date(2026, 10, 15))
    assert (out / "2026-10.md").read_text() == "# my own note\n"
    assert export(s, out, today=date(2026, 10, 15)) == 0  # nothing changed, nothing written
    s.delete_queue(1)
    export(s, out, today=date(2026, 10, 15))
    assert "alpha *(deleted)*" in (out / "2026-10-01.md").read_text()
