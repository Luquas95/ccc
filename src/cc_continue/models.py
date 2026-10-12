from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class QueueStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_RETRY = "waiting_retry"
    BLOCKED_ERROR = "blocked_error"
    # Hit a usage limit with auto-continue off: waits for the user (r / a
    # new message) even after the limit resets.
    PAUSED_LIMIT = "paused_limit"


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


class DeliveryMode(str, Enum):
    # Runs `claude -p --resume` as a separate headless subprocess. Safe,
    # gives real structured results (tokens/cost/success), but its
    # response never appears in any interactive terminal — only in
    # CC-continue's own history.
    HEADLESS = "headless"
    # Types the prompt directly into a live interactive session's own
    # tmux pane via `tmux send-keys`, so it visibly continues that
    # terminal's conversation. Riskier (see live_delivery module) and
    # gives no structured result — only "delivered" or "failed".
    LIVE_TERMINAL = "live_terminal"


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
    delivery_mode: DeliveryMode = DeliveryMode.HEADLESS
    # Flags passed to `claude` on every run (permissions, model, effort...)
    # for conversations started from the TUI. None = queue predates launch
    # attributes; the runner then uses its legacy flags.
    launch_flags: list[str] | None = None
    # One-shot flags for the first successful run only (--fork-session,
    # --from-pr ...). Cleared once the daemon adopts the session id Claude
    # Code returned for that run.
    first_run_flags: list[str] | None = None
    # Resume by itself once a usage limit resets (else PAUSED_LIMIT).
    auto_continue: bool = True
    # Manually paused from the Tasks editor: start no further items.
    paused: bool = False
    # Hidden from the TUI lists (still processed by the daemon).
    archived: bool = False
    # When the conversation was last shown in the TUI ("new reply" marker).
    last_seen_at: datetime | None = None


@dataclass
class QueueItem:
    id: int
    queue_id: int
    prompt_text: str
    position: int
    status: ItemStatus = ItemStatus.PENDING
    added_at: datetime = field(default_factory=datetime.now)
    # A usage limit interrupted this item after it reached the conversation:
    # the retry sends the continue text instead of repeating the prompt.
    continue_on_retry: bool = False


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
