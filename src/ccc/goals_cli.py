"""`ccc goal …` — goal loops from the shell and scripts: start one (the
daemon runs it), list them, stop one. With --wait the exit code says how
it ended: 0 met, 1 anything else."""
from __future__ import annotations

import argparse
import time

from ccc import goals
from ccc.i18n import _
from ccc.models import GoalStatus
from ccc.routines_cli import conversation_id

WAIT_POLL_SECONDS = 5.0


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("goal", help=_("Work towards a goal in rounds until a reviewer says it's met"))
    sub = parser.add_subparsers(dest="goal_command", required=True)
    start = sub.add_parser("start", help=_("Give a conversation a goal (the daemon runs the rounds)"))
    start.add_argument("conversation", help=_("the conversation: its id or name"))
    start.add_argument("goal")
    start.add_argument("--check", default="", help=_("a command run after each round, e.g. \"pytest -q\""))
    start.add_argument("--rounds", type=int, default=goals.DEFAULT_ROUNDS, help=_("at most this many rounds"))
    start.add_argument("--wait", action="store_true", help=_("wait until it ends; exit code 0 when the goal is met"))
    listing = sub.add_parser("list", help=_("Goals, newest first"))
    listing.add_argument("conversation", nargs="?", default=None)
    stop = sub.add_parser("stop", help=_("Stop the conversation's goal"))
    stop.add_argument("conversation")


def _line(goal) -> str:
    when = goal.created_at.strftime("%Y-%m-%d %H:%M")
    state = _(goals.STATUS_LABELS[goal.status])
    return f"{goal.id:>4}  {when}  {goal.round}/{goal.max_rounds}  {state:<14}  {goal.goal.splitlines()[0][:70]}"


def wait(storage, goal_id: int, sleep=time.sleep) -> int:
    while True:
        goal = storage.get_goal(goal_id)
        if goal.status != GoalStatus.RUNNING:
            print(_line(goal))
            if goal.last_reason:
                print(goal.last_reason)
            return 0 if goal.status == GoalStatus.PASSED else 1
        sleep(WAIT_POLL_SECONDS)


def run(storage, args: argparse.Namespace, sleep=time.sleep) -> int:
    command = args.goal_command
    try:
        if command == "start":
            goal = goals.start(storage, conversation_id(storage, args.conversation), args.goal, args.check, args.rounds)
            print(_("Goal {id} set — its first task is in the conversation's queue.").format(id=goal.id))
            return wait(storage, goal.id, sleep) if args.wait else 0
        if command == "list":
            queue_id = conversation_id(storage, args.conversation, include_archived=True) if args.conversation else None
            items = storage.list_goals(queue_id)
            for goal in items:
                print(_line(goal))
            if not items:
                print(_("No goals yet."))
            return 0
        if command == "stop":
            stopped = goals.stop(storage, conversation_id(storage, args.conversation, include_archived=True))
            print(_("Goal stopped.") if stopped else _("No goal is running there."))
            return 0
    except ValueError as error:
        print(error)
        return 1
    return 2
