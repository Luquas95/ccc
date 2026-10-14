"""Daily backups of the ccc database (history, settings — including the
Telegram token, hence private permissions). Uses SQLite's online backup
API, so the copy is consistent even while the daemon is writing."""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

KEEP_BACKUPS = 14


def default_backup_dir(db_path: str | Path) -> Path:
    return Path(db_path).parent / "backups"


def backup_path(out_dir: Path, today: date) -> Path:
    return out_dir / f"history-{today.isoformat()}.db"


def backup_now(db_path: str | Path, out_dir: Path, today: date | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)
    target = backup_path(out_dir, today or date.today())
    tmp = target.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    # Create the file private before any data lands in it.
    os.close(os.open(tmp, os.O_CREAT | os.O_WRONLY, 0o600))
    source = sqlite3.connect(str(db_path), timeout=30)
    dest = sqlite3.connect(str(tmp))
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    return target


def prune(out_dir: Path, keep: int = KEEP_BACKUPS) -> None:
    backups = sorted(out_dir.glob("history-*.db"))
    for old in backups[:-keep] if keep else backups:
        old.unlink(missing_ok=True)


def daily_backup(db_path: str | Path, out_dir: Path, today: date | None = None) -> Path | None:
    """Back up once per day; None if today's backup already exists."""
    today = today or date.today()
    if backup_path(out_dir, today).exists():
        return None
    path = backup_now(db_path, out_dir, today)
    prune(out_dir)
    return path
