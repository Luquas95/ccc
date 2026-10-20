"""Routines: prompts ccc queues on a schedule — a nightly review, an
hourly check, a summary on weekdays at six.

A routine belongs to a conversation. When it's due the daemon (tick())
either adds its prompt to that conversation's task queue (target SAME),
or starts a new headless conversation in the same folder, with the same
launch flags, for that one run and archives it once it's done (FRESH: a
clean context every time). Everything else — usage limits, commits,
notifications — is the queue's, as for any task.

- A schedule is a kind and a value (KINDS: every N minutes, daily at
  18:00, weekly on monday 08:00, a cron pattern…), kept as a cron
  pattern (ccc.cron) that gives the next run.
- Missed runs (the daemon or the computer was off) are caught up once,
  not once per missed time.
- While the previous run of a routine still goes, a new one is skipped
  (and counted): two runs of the same prompt would only get in each
  other's way."""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from ccc.cron import Cron
from ccc.i18n import N_, _
from ccc.models import DeliveryMode, QueueStatus, Routine, RoutineTarget

# (kind, label, value hint) — the schedules offered.
MINUTES, HOURS, DAILY, WEEKDAYS, WEEKLY, CRON = "minutes", "hours", "daily", "weekdays", "weekly", "cron"
KINDS: list[tuple[str, str, str]] = [
    (MINUTES, N_("Every N minutes"), N_("e.g. 30")),
    (HOURS, N_("Every N hours"), N_("e.g. 2")),
    (DAILY, N_("Every day at"), N_("e.g. 18:00")),
    (WEEKDAYS, N_("Monday to Friday at"), N_("e.g. 18:00")),
    (WEEKLY, N_("Once a week"), N_("e.g. monday 08:00")),
    (CRON, N_("Cron pattern"), N_("e.g. 0 22 * * *")),
]
KIND_IDS = [kind for kind, _label, _hint in KINDS]

# What the last firing did (Routine.last_status).
STATUS_QUEUED = "queued"
STATUS_STARTED = "started"  # FRESH: a new conversation
STATUS_SKIPPED = "skipped"  # the previous run still went
STATUS_ARCHIVED = "archived"  # its conversation is archived: nothing runs
STATUS_LABELS = {
    STATUS_QUEUED: N_("queued in its conversation"),
    STATUS_STARTED: N_("started a new conversation"),
    STATUS_SKIPPED: N_("skipped — the previous run was still going"),
    STATUS_ARCHIVED: N_("not run — its conversation is archived"),
}

_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")
# Day names as typed (English and Czech, with or without accents) → cron's 0-6.
_DAY_NAMES = {
    0: ("sunday", "sun", "su", "neděle", "nedele", "ne"),
    1: ("monday", "mon", "mo", "pondělí", "pondeli", "po"),
    2: ("tuesday", "tue", "tu", "úterý", "utery", "út", "ut"),
    3: ("wednesday", "wed", "we", "středa", "streda", "st"),
    4: ("thursday", "thu", "th", "čtvrtek", "ctvrtek", "čt", "ct"),
    5: ("friday", "fri", "fr", "pátek", "patek", "pá", "pa"),
    6: ("saturday", "sat", "sa", "sobota", "so"),
}
_DAYS = {name: day for day, names in _DAY_NAMES.items() for name in names}
_WEEKDAY_LABELS = [N_("Sundays"), N_("Mondays"), N_("Tuesdays"), N_("Wednesdays"), N_("Thursdays"),
                   N_("Fridays"), N_("Saturdays")]


def _time(text: str) -> tuple[int, int]:
    match = _TIME.match(text.strip())
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        raise ValueError(_("“{text}” isn't a time — write it as HH:MM, e.g. 18:00.").format(text=text.strip()))
    return int(match.group(1)), int(match.group(2))


def _count(text: str, unit_max: int) -> int:
    """N for "every N minutes / hours": it must divide the hour / day evenly,
    so the runs stay evenly spaced (cron restarts the count each hour)."""
    if not text.strip().isdigit() or not 1 <= int(text) <= unit_max:
        raise ValueError(_("Write a whole number from 1 to {max}.").format(max=unit_max))
    n = int(text)
    if (unit_max + 1) % n:
        raise ValueError(_("{n} doesn't divide {total} evenly — pick e.g. {examples}.").format(
            n=n, total=unit_max + 1, examples="5, 10, 15, 20, 30" if unit_max == 59 else "1, 2, 3, 4, 6, 8, 12"))
    return n


def to_cron(kind: str, value: str) -> str:
    """The cron pattern of a schedule; ValueError with a message for the user."""
    value = value.strip()
    if kind == MINUTES:
        n = _count(value, 59)
        return "* * * * *" if n == 1 else f"*/{n} * * * *"
    if kind == HOURS:
        n = _count(value, 23)
        return "0 * * * *" if n == 1 else f"0 */{n} * * *"
    if kind in (DAILY, WEEKDAYS):
        hour, minute = _time(value or "09:00")
        return f"{minute} {hour} * * {'*' if kind == DAILY else '1-5'}"
    if kind == WEEKLY:
        day_text, _sep, time_text = value.partition(" ")
        day = _DAYS.get(day_text.strip().lower())
        if day is None:
            raise ValueError(_("“{text}” isn't a day — write e.g. monday 08:00.").format(text=day_text))
        hour, minute = _time(time_text or "09:00")
        return f"{minute} {hour} * * {day}"
    if kind == CRON:
        Cron.parse(value)
        return " ".join(value.split())
    raise ValueError(f"unknown schedule kind {kind!r}")


def describe(kind: str, value: str) -> str:
    """The schedule in words ("every day at 18:00")."""
    value = value.strip()
    if kind == MINUTES:
        return _("every {n} min").format(n=int(value))
    if kind == HOURS:
        return _("every {n} h").format(n=int(value))
    if kind in (DAILY, WEEKDAYS):
        hour, minute = _time(value or "09:00")
        text = _("every day at {time}") if kind == DAILY else _("Mon–Fri at {time}")
        return text.format(time=f"{hour:02d}:{minute:02d}")
    if kind == WEEKLY:
        day_text, _sep, time_text = value.partition(" ")
        hour, minute = _time(time_text or "09:00")
        return _("{days} at {time}").format(days=_(_WEEKDAY_LABELS[_DAYS[day_text.lower()]]),
                                            time=f"{hour:02d}:{minute:02d}")
    return f"cron {value}"


def next_run(cron: str, after: datetime) -> datetime | None:
    return Cron.parse(cron).next_after(after)


def add(storage, queue_id: int, name: str, prompt_text: str, kind: str, value: str,
        target: RoutineTarget = RoutineTarget.SAME, now: datetime | None = None) -> Routine:
    """Create a routine (ValueError for a schedule or text that won't do)."""
    if not prompt_text.strip():
        raise ValueError(_("The routine needs a prompt."))
    if storage.find_queue(queue_id) is None:
        raise ValueError(_("That conversation doesn't exist."))
    cron = to_cron(kind, value)
    name = name.strip() or prompt_text.strip().splitlines()[0][:40]
    return storage.add_routine(queue_id, name, prompt_text.strip(), kind, value.strip(), cron, target,
                               next_run(cron, now or datetime.now()))


def update(storage, routine_id: int, *, queue_id: int, name: str, prompt_text: str, kind: str, value: str,
           target: RoutineTarget, now: datetime | None = None) -> None:
    if not prompt_text.strip():
        raise ValueError(_("The routine needs a prompt."))
    cron = to_cron(kind, value)
    storage.update_routine(
        routine_id, queue_id=queue_id, name=name.strip() or prompt_text.strip().splitlines()[0][:40],
        prompt_text=prompt_text.strip(), schedule_kind=kind, schedule_value=value.strip(), cron=cron,
        target=target, next_run_at=next_run(cron, now or datetime.now()),
    )


def set_enabled(storage, routine_id: int, enabled: bool, now: datetime | None = None) -> None:
    """On / off. Turned on, it next runs at its next time from now — never
    at once for the times it was off."""
    routine = storage.get_routine(routine_id)
    storage.update_routine(routine_id, enabled=enabled,
                           next_run_at=next_run(routine.cron, now or datetime.now()) if enabled else None)


def running(storage, routine: Routine) -> bool:
    """The routine's previous run hasn't finished yet."""
    if storage.routine_items_active(routine.id):
        return True
    return any(q.status in (QueueStatus.RUNNING, QueueStatus.WAITING_RETRY)
               for q in storage.routine_queues(routine.id, archived=False))


def fire(storage, routine: Routine, now: datetime | None = None) -> str:
    """Queue one run of the routine now (STATUS_*). Doesn't move its
    next scheduled time — tick() does."""
    now = now or datetime.now()
    owner = storage.find_queue(routine.queue_id)
    if owner is None or owner.archived:
        status = STATUS_ARCHIVED
    elif running(storage, routine):
        status = STATUS_SKIPPED
        storage.update_routine(routine.id, skipped=routine.skipped + 1)
    elif routine.target == RoutineTarget.FRESH:
        queue = storage.create_queue(
            f"{routine.name} · {now:%Y-%m-%d %H:%M}", owner.project_path, str(uuid.uuid4()),
            delivery_mode=DeliveryMode.HEADLESS, launch_flags=owner.launch_flags,
            auto_continue=owner.auto_continue, routine_id=routine.id,
        )
        storage.add_queue_item(queue.id, routine.prompt_text, routine_id=routine.id)
        status = STATUS_STARTED
    else:
        storage.add_queue_item(owner.id, routine.prompt_text, routine_id=routine.id)
        status = STATUS_QUEUED
    storage.update_routine(routine.id, last_run_at=now, last_status=status)
    return status


def archive_finished(storage) -> list[int]:
    """Archive conversations routines started (FRESH) once their run is
    done. A blocked one stays, so you see what went wrong."""
    archived = []
    for queue in storage.routine_queues(archived=False):
        if queue.status == QueueStatus.IDLE and storage.count_pending_items(queue.id) == 0 \
                and not storage.routine_items_active(queue.routine_id):
            storage.set_queue_archived(queue.id, True)
            archived.append(queue.id)
    return archived


def tick(storage, now: datetime | None = None) -> list[tuple[Routine, str]]:
    """Fire every routine that's due — once, however many times it was
    missed — and set its next time. Returns what fired and how."""
    now = now or datetime.now()
    fired = []
    for routine in storage.list_routines():
        if not routine.enabled or routine.next_run_at is None or routine.next_run_at > now:
            continue
        status = fire(storage, routine, now)
        storage.update_routine(routine.id, next_run_at=next_run(routine.cron, now))
        fired.append((routine, status))
    archive_finished(storage)
    return fired


def find(storage, ref: str) -> Routine | None:
    """A routine by id or name (for the command line)."""
    if ref.isdigit():
        return storage.find_routine(int(ref))
    matches = [r for r in storage.list_routines() if r.name == ref]
    return matches[0] if len(matches) == 1 else None
