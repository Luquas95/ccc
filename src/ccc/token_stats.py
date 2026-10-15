"""Token history by calendar month and day, for the Analytics screen and the
Obsidian export. Numbers come from Storage.token_entries (headless runs and
remote-control replies, deleted conversations included)."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ConversationTokens:
    queue_id: int
    name: str
    deleted: bool
    tokens: int
    success: int = 0
    errors: int = 0
    rate_limited: int = 0


@dataclass
class PeriodStats:
    total: int = 0
    by_day: dict[date, int] = field(default_factory=dict)
    by_model: list[tuple[str, int]] = field(default_factory=list)  # descending
    by_conversation: list[ConversationTokens] = field(default_factory=list)  # descending


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    return start, end


def shift_month(year: int, month: int, step: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + step
    return index // 12, index % 12 + 1


def _stats(storage, start: date, end: date) -> PeriodStats:
    entries = storage.token_entries(start.isoformat(), end.isoformat())
    names = storage.conversation_names()
    statuses = storage.run_status_counts(start.isoformat(), end.isoformat())
    by_day: Counter = Counter()
    by_model: Counter = Counter()
    by_queue: Counter = Counter()
    for day, queue_id, model, tokens in entries:
        by_day[date.fromisoformat(day)] += tokens
        by_model[model] += tokens
        by_queue[queue_id] += tokens
    conversations = []
    for queue_id in set(by_queue) | set(statuses):
        name, deleted = names.get(queue_id, (f"conversation {queue_id}", True))
        success, errors, limited = statuses.get(queue_id, (0, 0, 0))
        conversations.append(ConversationTokens(queue_id, name, deleted, by_queue[queue_id], success, errors, limited))
    conversations.sort(key=lambda c: (-c.tokens, c.name))
    return PeriodStats(
        total=sum(by_day.values()),
        by_day=dict(sorted(by_day.items())),
        by_model=sorted(by_model.items(), key=lambda kv: (-kv[1], kv[0])),
        by_conversation=conversations,
    )


def month_stats(storage, year: int, month: int) -> PeriodStats:
    return _stats(storage, *month_bounds(year, month))


def day_stats(storage, day: date) -> PeriodStats:
    from datetime import timedelta

    return _stats(storage, day, day + timedelta(days=1))


def months(storage) -> list[tuple[int, int, int]]:
    """(year, month, tokens) of every month with usage, newest first."""
    totals: defaultdict[tuple[int, int], int] = defaultdict(int)
    for day, _queue, _model, tokens in storage.token_entries():
        totals[(int(day[:4]), int(day[5:7]))] += tokens
    return [(y, m, t) for (y, m), t in sorted(totals.items(), reverse=True)]
