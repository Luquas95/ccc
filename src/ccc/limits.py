"""Turn the account's usage (usage_api.ProUsage) into "wait until" times
for the daemon. Pure functions, no I/O. Inputs from the usage API are
aware UTC datetimes; `now` and every result are naive local time, like
queues.next_retry_at."""
from __future__ import annotations

from datetime import datetime, timedelta

from ccc.usage_api import ProUsage

# Margin after the advertised reset before trying again, so the first run
# doesn't race the limit window rolling over.
RESET_BUFFER = timedelta(seconds=30)


def _windows(usage: ProUsage | None) -> list:
    if usage is None:
        return []
    found = [w for w in (usage.five_hour, usage.seven_day) if w is not None]
    return found + list(usage.per_model)


def _local(dt: datetime) -> datetime:
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def exhausted_until(usage: ProUsage | None, now: datetime, threshold: float = 100) -> datetime | None:
    """If any limit window is at or above `threshold` percent (100 = used
    up; lower = the user's reserve), when the last of them resets (plus
    RESET_BUFFER); None when none is, or usage is unknown."""
    resets = [_local(w.resets_at) + RESET_BUFFER for w in _windows(usage) if w.utilization_pct >= threshold]
    resets = [r for r in resets if r > now]
    return max(resets) if resets else None


def retry_time_after_rate_limit(usage: ProUsage | None, now: datetime) -> datetime | None:
    """After Claude Code reported a usage-limit hit: the reset of the
    busiest window (usage figures can lag slightly behind the 429, so the
    busiest one is taken even below 100%). None if usage is unknown or
    that reset is already past — callers fall back to other heuristics."""
    windows = _windows(usage)
    if not windows:
        return None
    busiest = max(windows, key=lambda w: w.utilization_pct)
    at = _local(busiest.resets_at) + RESET_BUFFER
    return at if at > now else None
