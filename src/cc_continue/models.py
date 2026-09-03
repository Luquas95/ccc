from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class QueueStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_RETRY = "waiting_retry"
    BLOCKED_ERROR = "blocked_error"


class ItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(str, Enum):
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class Queue:
    id: int
    name: str
    project_path: str
    session_id: str
    status: QueueStatus = QueueStatus.IDLE
    next_retry_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    # True for a queue attached to a session that already existed before
    # CC-continue touched it (discovered via `claude agents`) — its first
    # prompt must use --resume, never --session-id, since the ID isn't new.
    always_resume: bool = False


@dataclass
class QueueItem:
    id: int
    queue_id: int
    prompt_text: str
    position: int
    status: ItemStatus = ItemStatus.PENDING
    added_at: datetime = field(default_factory=datetime.now)


@dataclass
class PromptRun:
    id: int
    queue_id: int
    queue_item_id: int | None
    prompt_text: str
    started_at: datetime
    finished_at: datetime | None
    status: RunStatus
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    duration_ms: int = 0
    num_turns: int = 0
    result_text: str | None = None
    error_text: str | None = None
