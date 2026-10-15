from datetime import date, datetime

from ccc.analytics_archive import FOLDER_KEY, archive, configured_folder
from ccc.models import PromptRun, RunStatus
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


def test_only_finished_months_are_archived(tmp_path):
    s = _storage(tmp_path)
    out = tmp_path / "analytics"
    assert archive(s, out, today=date(2026, 10, 15)) == [(2026, 9)]
    assert sorted(p.name for p in out.iterdir()) == ["2026-09-30.md", "2026-09.md", "ccc_analytics.md"]
    index = (out / "ccc_analytics.md").read_text()
    assert "[[2026-09\\|September 2026]] | 100" in index and "2026-10" not in index.split("## Months")[1]
    day = (out / "2026-09-30.md").read_text()
    assert "beta\\|pipe" in day and "[[2026-09|September 2026]]" in day
    assert "[[2026-09-30\\|30]]<br>100" in (out / "2026-09.md").read_text()

    # the next month starts: October gets archived, September stays as it was
    assert archive(s, out, today=date(2026, 11, 1)) == [(2026, 10)]
    month = (out / "2026-10.md").read_text()
    assert "**1 500 000 tokens**" in month and "| alpha | 1 500 000 | 1 | 0 |" in month and "xychart-beta" in month
    assert "[[2026-10\\|October 2026]] | 1 500 000" in (out / "ccc_analytics.md").read_text()
    assert archive(s, out, today=date(2026, 11, 2)) == []


def test_archive_is_written_once_and_foreign_files_left_alone(tmp_path):
    s = _storage(tmp_path)
    out = tmp_path / "analytics"
    out.mkdir()
    (out / "ccc_analytics.md").write_text("# my own note\n")
    archive(s, out, today=date(2026, 11, 1))
    assert (out / "ccc_analytics.md").read_text() == "# my own note\n"
    s.delete_queue(1)  # later changes don't rewrite an archived month
    before = (out / "2026-10-01.md").read_text()
    archive(s, out, today=date(2026, 12, 1))
    assert (out / "2026-10-01.md").read_text() == before
    (out / "2026-10.md").unlink()  # deleted by hand -> written again
    assert archive(s, out, today=date(2026, 12, 1)) == [(2026, 10)]


def test_default_folder_is_next_to_the_database(tmp_path):
    s = Storage(tmp_path / "h.db")
    assert configured_folder(s) == tmp_path / "analytics"
    s.set_setting(FOLDER_KEY, str(tmp_path / "vault" / "ccc"))
    assert configured_folder(s) == tmp_path / "vault" / "ccc"
