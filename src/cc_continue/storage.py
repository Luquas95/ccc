from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from cc_continue.models import ItemStatus, PromptRun, Queue, QueueItem, QueueStatus, RunStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS queues (
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

CREATE TABLE IF NOT EXISTS queue_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL REFERENCES queues(id),
    prompt_text TEXT NOT NULL,
    position INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id INTEGER NOT NULL REFERENCES queues(id),
    queue_item_id INTEGER,
    prompt_text TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    cost_usd REAL NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    num_turns INTEGER NOT NULL DEFAULT 0,
    result_text TEXT,
    error_text TEXT
);
"""


class Storage:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        # timeout: wait for another process's write lock instead of raising
        # "database is locked" immediately — needed once the daemon and a
        # TUI instance can both be writing to the same file concurrently.
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def create_queue(self, name: str, project_path: str, session_id: str) -> Queue:
        now = datetime.now().isoformat()
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO queues (name, project_path, session_id, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, project_path, session_id, QueueStatus.IDLE.value, now, now),
            )
            conn.commit()
            queue_id = cur.lastrowid
        return self.get_queue(queue_id)

    def get_queue_by_path(self, project_path: str) -> Queue | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM queues WHERE project_path = ?", (project_path,)).fetchone()
            return self._row_to_queue(row) if row else None

    def get_queue(self, queue_id: int) -> Queue:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM queues WHERE id = ?", (queue_id,)).fetchone()
            return self._row_to_queue(row)

    def list_queues(self) -> list[Queue]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM queues ORDER BY name").fetchall()
            return [self._row_to_queue(r) for r in rows]

    def update_queue_status(
        self,
        queue_id: int,
        status: QueueStatus,
        next_retry_at: datetime | None = None,
        last_error: str | None = None,
    ) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE queues SET status = ?, next_retry_at = ?, last_error = ?, updated_at = ? WHERE id = ?",
                (
                    status.value,
                    next_retry_at.isoformat() if next_retry_at else None,
                    last_error,
                    datetime.now().isoformat(),
                    queue_id,
                ),
            )
            conn.commit()

    def add_queue_item(self, queue_id: int, prompt_text: str) -> QueueItem:
        with closing(self._connect()) as conn:
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM queue_items WHERE queue_id = ?", (queue_id,)
            ).fetchone()[0]
            now = datetime.now().isoformat()
            cur = conn.execute(
                "INSERT INTO queue_items (queue_id, prompt_text, position, status, added_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (queue_id, prompt_text, max_pos + 1, ItemStatus.PENDING.value, now),
            )
            conn.commit()
            item_id = cur.lastrowid
            row = conn.execute("SELECT * FROM queue_items WHERE id = ?", (item_id,)).fetchone()
            return self._row_to_item(row)

    def next_pending_item(self, queue_id: int) -> QueueItem | None:
        """Read-only peek at the next pending item (for display). Does not
        claim it — two callers can see the same item. Use
        claim_next_pending_item() to actually take ownership of one."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM queue_items WHERE queue_id = ? AND status = ? ORDER BY position LIMIT 1",
                (queue_id, ItemStatus.PENDING.value),
            ).fetchone()
            return self._row_to_item(row) if row else None

    def claim_next_pending_item(self, queue_id: int) -> QueueItem | None:
        """Atomically transition the oldest pending item to 'running' and
        return it. Safe to call from multiple processes against the same
        SQLite file at once — SQLite's write lock makes the UPDATE...WHERE
        a single atomic claim, so at most one caller ever gets a given item
        (everyone else's UPDATE matches zero rows and gets None back)."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "UPDATE queue_items SET status = ? "
                "WHERE id = ("
                "  SELECT id FROM queue_items WHERE queue_id = ? AND status = ? "
                "  ORDER BY position LIMIT 1"
                ") AND status = ? "
                "RETURNING *",
                (
                    ItemStatus.RUNNING.value,
                    queue_id,
                    ItemStatus.PENDING.value,
                    ItemStatus.PENDING.value,
                ),
            ).fetchone()
            conn.commit()
            return self._row_to_item(row) if row else None

    def count_pending_items(self, queue_id: int) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM queue_items WHERE queue_id = ? AND status = ?",
                (queue_id, ItemStatus.PENDING.value),
            ).fetchone()
            return row[0]

    def set_item_status(self, item_id: int, status: ItemStatus) -> None:
        with closing(self._connect()) as conn:
            conn.execute("UPDATE queue_items SET status = ? WHERE id = ?", (status.value, item_id))
            conn.commit()

    def reset_running_items_to_pending(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE queue_items SET status = ? WHERE status = ?",
                (ItemStatus.PENDING.value, ItemStatus.RUNNING.value),
            )
            conn.execute(
                "UPDATE queues SET status = ? WHERE status = ?",
                (QueueStatus.IDLE.value, QueueStatus.RUNNING.value),
            )
            conn.commit()

    def insert_prompt_run(self, run: PromptRun) -> int:
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO prompt_runs (queue_id, queue_item_id, prompt_text, started_at, finished_at, "
                "status, cost_usd, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, "
                "duration_ms, num_turns, result_text, error_text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.queue_id,
                    run.queue_item_id,
                    run.prompt_text,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat() if run.finished_at else None,
                    run.status.value,
                    run.cost_usd,
                    run.input_tokens,
                    run.output_tokens,
                    run.cache_read_tokens,
                    run.cache_creation_tokens,
                    run.duration_ms,
                    run.num_turns,
                    run.result_text,
                    run.error_text,
                ),
            )
            conn.commit()
            return cur.lastrowid

    def runs_for_queue(self, queue_id: int) -> list[PromptRun]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM prompt_runs WHERE queue_id = ? ORDER BY started_at DESC", (queue_id,)
            ).fetchall()
            return [self._row_to_run(r) for r in rows]

    def daily_cost_totals(self, days: int = 30) -> list[tuple[str, float]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT substr(started_at, 1, 10) AS day, SUM(cost_usd) FROM prompt_runs "
                "WHERE started_at >= date('now', ?) GROUP BY day ORDER BY day",
                (f"-{days} days",),
            ).fetchall()
            return [(r[0], r[1]) for r in rows]

    def daily_token_totals(self, days: int = 30) -> list[tuple[str, int]]:
        """Total tokens (input+output+cache_read+cache_creation) per day —
        a more honest usage indicator than cost_usd for a subscription
        plan, since it reflects the same pool the account's usage limit
        actually draws from, not a notional per-token dollar price."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT substr(started_at, 1, 10) AS day, "
                "SUM(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens) "
                "FROM prompt_runs WHERE started_at >= date('now', ?) GROUP BY day ORDER BY day",
                (f"-{days} days",),
            ).fetchall()
            return [(r[0], r[1] or 0) for r in rows]

    def blocked_seconds_total(self) -> float:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT SUM((julianday(finished_at) - julianday(started_at)) * 86400) "
                "FROM prompt_runs WHERE status = ? AND finished_at IS NOT NULL",
                (RunStatus.RATE_LIMITED.value,),
            ).fetchone()
            return row[0] or 0.0

    @staticmethod
    def _row_to_queue(row: sqlite3.Row) -> Queue:
        return Queue(
            id=row["id"],
            name=row["name"],
            project_path=row["project_path"],
            session_id=row["session_id"],
            status=QueueStatus(row["status"]),
            next_retry_at=datetime.fromisoformat(row["next_retry_at"]) if row["next_retry_at"] else None,
            last_error=row["last_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> QueueItem:
        return QueueItem(
            id=row["id"],
            queue_id=row["queue_id"],
            prompt_text=row["prompt_text"],
            position=row["position"],
            status=ItemStatus(row["status"]),
            added_at=datetime.fromisoformat(row["added_at"]),
        )

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> PromptRun:
        return PromptRun(
            id=row["id"],
            queue_id=row["queue_id"],
            queue_item_id=row["queue_item_id"],
            prompt_text=row["prompt_text"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
            status=RunStatus(row["status"]),
            cost_usd=row["cost_usd"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cache_read_tokens=row["cache_read_tokens"],
            cache_creation_tokens=row["cache_creation_tokens"],
            duration_ms=row["duration_ms"],
            num_turns=row["num_turns"],
            result_text=row["result_text"],
            error_text=row["error_text"],
        )
