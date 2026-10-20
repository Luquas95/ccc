"""`ccc routine …` — routines from the shell: list, add, run now, turn on
/ off, remove. The same as the Routines window (o); the daemon runs them."""
from __future__ import annotations

import argparse
import re
from datetime import datetime

from ccc import routines
from ccc.i18n import _
from ccc.models import RoutineTarget
from ccc.schedule import format_when

_EVERY = re.compile(r"^(\d+)\s*([mh])$")


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("routine", help=_("Prompts queued on a schedule (list, add, run, on, off, remove)"))
    sub = parser.add_subparsers(dest="routine_command", required=True)
    sub.add_parser("list", help=_("Every routine with its schedule and next run"))
    add = sub.add_parser("add", help=_("Add a routine to a conversation"))
    add.add_argument("conversation", help=_("the conversation: its id or name"))
    add.add_argument("prompt")
    add.add_argument("--name", default="")
    when = add.add_mutually_exclusive_group(required=True)
    when.add_argument("--every", help=_("30m, 2h …"))
    when.add_argument("--hourly", action="store_true")
    when.add_argument("--daily", nargs="?", const="09:00", metavar="HH:MM")
    when.add_argument("--weekdays", nargs="?", const="09:00", metavar="HH:MM")
    when.add_argument("--on", metavar='"DAY [HH:MM]"', help=_("once a week, e.g. \"monday 08:00\""))
    when.add_argument("--cron", metavar="PATTERN", help=_("a 5-field cron pattern, e.g. \"0 22 * * *\""))
    add.add_argument("--fresh", action="store_true",
                     help=_("a new conversation in the same folder every run (archived when done)"))
    for name, text in (("run", _("Run a routine now")), ("on", _("Turn a routine on")),
                       ("off", _("Turn a routine off")), ("remove", _("Delete a routine"))):
        command = sub.add_parser(name, help=text)
        command.add_argument("routine", help=_("its id or name (see `ccc routine list`)"))


def _schedule(args) -> tuple[str, str]:
    if args.every:
        match = _EVERY.match(args.every.strip().lower())
        if not match:
            raise ValueError(_("--every takes minutes or hours, e.g. 30m or 2h."))
        return (routines.MINUTES if match.group(2) == "m" else routines.HOURS), match.group(1)
    if args.hourly:
        return routines.HOURS, "1"
    if args.daily:
        return routines.DAILY, args.daily
    if args.weekdays:
        return routines.WEEKDAYS, args.weekdays
    if args.on:
        return routines.WEEKLY, args.on
    return routines.CRON, args.cron


def conversation_id(storage, ref: str, include_archived: bool = False) -> int:
    """A conversation by id or exact name (ValueError otherwise)."""
    queues = [q for q in storage.list_queues()
              if (include_archived or not q.archived) and q.routine_id is None]
    if ref.isdigit() and any(q.id == int(ref) for q in queues):
        return int(ref)
    named = [q for q in queues if q.name == ref]
    if len(named) == 1:
        return named[0].id
    raise ValueError(_("No single active conversation “{ref}” — use its id or exact name.").format(ref=ref))


def run(storage, args: argparse.Namespace) -> int:
    command = args.routine_command
    if command == "list":
        now = datetime.now()
        names = {q.id: q.name for q in storage.list_queues()}
        items = storage.list_routines()
        for r in items:
            state = "●" if r.enabled else "○"
            fresh = " ✚" if r.target == RoutineTarget.FRESH else ""
            nxt = format_when(r.next_run_at, now) if r.enabled else "—"
            print(f"{r.id:>3} {state} {r.name}{fresh} · {names.get(r.queue_id, '?')} · "
                  f"{routines.describe(r.schedule_kind, r.schedule_value)} · {_('next: {at}').format(at=nxt)}")
        if not items:
            print(_("No routines yet."))
        return 0
    try:
        if command == "add":
            kind, value = _schedule(args)
            target = RoutineTarget.FRESH if args.fresh else RoutineTarget.SAME
            routine = routines.add(storage, conversation_id(storage, args.conversation), args.name, args.prompt,
                                   kind, value, target)
            print(_("Routine {id} added — next run {at}.").format(
                id=routine.id, at=format_when(routine.next_run_at, datetime.now())))
            return 0
        routine = routines.find(storage, args.routine)
        if routine is None:
            raise ValueError(_("No routine “{ref}” — see `ccc routine list`.").format(ref=args.routine))
        if command == "run":
            status = routines.fire(storage, routine)
            print(_(routines.STATUS_LABELS[status]))
            return 0 if status in (routines.STATUS_QUEUED, routines.STATUS_STARTED) else 1
        if command in ("on", "off"):
            routines.set_enabled(storage, routine.id, command == "on")
            message = _("Routine {id} is on.") if command == "on" else _("Routine {id} is off.")
            print(message.format(id=routine.id))
            return 0
        if command == "remove":
            storage.delete_routine(routine.id)
            print(_("Routine {id} deleted.").format(id=routine.id))
            return 0
    except ValueError as error:
        print(error)
        return 1
    return 2
