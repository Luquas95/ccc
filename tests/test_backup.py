import asyncio
import os
import sqlite3
import stat
from datetime import date

from ccc.backup import backup_now, daily_backup, prune
from ccc.storage import Storage


def _db(tmp_path):
    storage = Storage(tmp_path / "history.db")
    storage.create_queue("a", "/tmp/a", "s1")
    storage.set_setting("telegram_token", "secret")
    return storage


def test_backup_is_consistent_copy_with_private_permissions(tmp_path):
    storage = _db(tmp_path)
    path = backup_now(storage.db_path, tmp_path / "backups", today=date(2026, 10, 14))
    assert path.name == "history-2026-10-14.db"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700
    copy = sqlite3.connect(path)
    assert copy.execute("select name from queues").fetchall() == [("a",)]


def test_daily_backup_runs_once_per_day(tmp_path):
    storage = _db(tmp_path)
    out = tmp_path / "backups"
    first = daily_backup(storage.db_path, out, today=date(2026, 10, 14))
    storage.create_queue("b", "/tmp/b", "s2")
    assert daily_backup(storage.db_path, out, today=date(2026, 10, 14)) is None  # already done today
    assert sqlite3.connect(first).execute("select count(*) from queues").fetchone()[0] == 1
    assert daily_backup(storage.db_path, out, today=date(2026, 10, 15)).name == "history-2026-10-15.db"


def test_prune_keeps_newest(tmp_path):
    out = tmp_path / "backups"
    out.mkdir()
    for day in range(1, 21):
        (out / f"history-2026-10-{day:02d}.db").write_text("x")
    (out / "unrelated.txt").write_text("keep me")
    prune(out, keep=14)
    names = sorted(p.name for p in out.glob("history-*.db"))
    assert len(names) == 14 and names[0] == "history-2026-10-07.db"
    assert (out / "unrelated.txt").exists()


def test_cli_backup(tmp_path, monkeypatch, capsys):
    from ccc import cli

    storage = _db(tmp_path)
    monkeypatch.setattr(cli, "default_db_path", lambda: tmp_path / "history.db")
    monkeypatch.setattr("ccc.backup.default_backup_dir", lambda db_path: tmp_path / "bk")
    cli.main(["backup"])
    out = capsys.readouterr().out
    assert "bk/history-" in out and list((tmp_path / "bk").glob("history-*.db"))


async def test_backup_loop_makes_todays_backup(tmp_path):
    from ccc.daemon import backup_loop

    storage = _db(tmp_path)
    task = asyncio.create_task(backup_loop(storage.db_path, tmp_path / "bk", interval=0.05))
    await asyncio.sleep(0.2)
    task.cancel()
    assert list((tmp_path / "bk").glob("history-*.db"))
