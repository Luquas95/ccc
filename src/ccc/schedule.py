"""When a queued task may start: parsing what the user typed in the task
editor ("HH:MM", "YYYY-MM-DD HH:MM", "reset") into a naive local time."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_when(text: str, now: datetime, reset_at: datetime | None = None) -> datetime | None:
    """None = as soon as possible. "reset" needs reset_at (the next 5-hour
    window reset from the usage API). Raises ValueError for anything else
    it can't read, with a message fit for the user."""
    text = text.strip()
    if not text:
        return None
    if text.lower() == "reset":
        if reset_at is None:
            raise ValueError("Usage data isn't available, so the next reset time is unknown.")
        return reset_at
    match = _HHMM.match(text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            raise ValueError(f"'{text}' isn't a valid time.")
        at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return at if at > now else at + timedelta(days=1)
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError(f"Use HH:MM, YYYY-MM-DD HH:MM or 'reset' — not '{text}'.") from None


def format_when(at: datetime | None, now: datetime) -> str:
    if at is None:
        return ""
    return at.strftime("%H:%M") if at.date() == now.date() else at.strftime("%Y-%m-%d %H:%M")
