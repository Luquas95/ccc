"""A small cron: the 5-field patterns routines run on ("0 22 * * *"),
in naive local time like the rest of ccc's scheduling.

Fields: minute hour day-of-month month day-of-week, each `*`, a number,
a range `a-b`, a list `a,b`, a step `*/n` or `a-b/n`; months and days
can be names (jan, mon). Day of week 0 or 7 is Sunday. As in classic
cron, when both day fields are restricted a day matching either runs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ccc.i18n import _

_MONTHS = {name: n for n, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_DAYS = {name: n for n, name in enumerate(("sun", "mon", "tue", "wed", "thu", "fri", "sat"))}
# (low, high, names) per field.
_FIELDS = ((0, 59, {}), (0, 23, {}), (1, 31, {}), (1, 12, _MONTHS), (0, 7, _DAYS))
# How far next_after() looks: every pattern that can run at all runs
# within this (Feb 29 on a given weekday comes round in 28 years).
_SEARCH_DAYS = 366 * 28


def _value(text: str, low: int, high: int, names: dict[str, int]) -> int:
    value = names.get(text.lower()) if not text.isdigit() else int(text)
    if value is None or not low <= value <= high:
        raise ValueError
    return value


def _field(text: str, low: int, high: int, names: dict[str, int]) -> frozenset[int]:
    values: set[int] = set()
    for part in text.split(","):
        base, _sep, step_text = part.partition("/")
        step = int(step_text) if step_text.isdigit() and int(step_text) > 0 else None
        if step_text and step is None:
            raise ValueError
        if base == "*":
            start, end = low, high
        elif "-" in base:
            first, _dash, last = base.partition("-")
            start, end = _value(first, low, high, names), _value(last, low, high, names)
            if start > end:
                raise ValueError
        else:
            start = _value(base, low, high, names)
            end = high if step else start
        values.update(range(start, end + 1, step or 1))
    return frozenset(values)


@dataclass(frozen=True)
class Cron:
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]  # 0 = Sunday … 6 = Saturday
    any_day: bool  # day of month is *
    any_weekday: bool  # day of week is *

    @classmethod
    def parse(cls, text: str) -> "Cron":
        """ValueError (with a message for the user) if it isn't a pattern."""
        parts = text.split()
        if len(parts) != 5:
            raise ValueError(_("A cron pattern has 5 fields (minute hour day month weekday), e.g. 0 22 * * *."))
        try:
            fields = [_field(part, *spec) for part, spec in zip(parts, _FIELDS)]
        except ValueError:
            raise ValueError(_("“{text}” isn't a cron pattern ccc can read.").format(text=text)) from None
        weekdays = frozenset(d % 7 for d in fields[4])
        cron = cls(fields[0], fields[1], fields[2], fields[3], weekdays, parts[2] == "*", parts[4] == "*")
        if cron.next_after(datetime(2000, 1, 1)) is None:
            raise ValueError(_("“{text}” never runs.").format(text=text))
        return cron

    def _day_matches(self, day: datetime) -> bool:
        if day.month not in self.months:
            return False
        in_month = day.day in self.days
        in_week = (day.isoweekday() % 7) in self.weekdays
        if self.any_day or self.any_weekday:
            return in_month and in_week
        return in_month or in_week

    def next_after(self, after: datetime) -> datetime | None:
        """The first matching minute strictly after `after`."""
        start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        day = start.replace(hour=0, minute=0)
        for offset in range(_SEARCH_DAYS):
            current = day + timedelta(days=offset)
            if not self._day_matches(current):
                continue
            for hour in sorted(self.hours):
                for minute in sorted(self.minutes):
                    at = current.replace(hour=hour, minute=minute)
                    if at >= start:
                        return at
        return None
