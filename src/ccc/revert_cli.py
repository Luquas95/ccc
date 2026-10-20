"""`ccc runs CONVERSATION` (its runs with their ids and commits) and
`ccc revert RUN [--tell]` (undo a run's commit, ccc.revert)."""
from __future__ import annotations

import argparse

from ccc import revert
from ccc.i18n import _
from ccc.routines_cli import conversation_id


def add_parser(subparsers) -> None:
    runs = subparsers.add_parser("runs", help=_("A conversation's runs: id, time, status, commit, task"))
    runs.add_argument("conversation", help=_("the conversation: its id or name"))
    undo = subparsers.add_parser("revert", help=_("Revert the commit of a run (a new commit; see `ccc runs`)"))
    undo.add_argument("run", type=int, help=_("the run's id"))
    undo.add_argument("--tell", action="store_true", help=_("also queue a note so Claude knows"))


def run_runs(storage, args: argparse.Namespace) -> int:
    try:
        queue_id = conversation_id(storage, args.conversation, include_archived=True)
    except ValueError as error:
        print(error)
        return 1
    for run in storage.runs_for_queue(queue_id):
        commit = run.git_commit[:7] if run.git_commit else "-"
        if run.reverted_by:
            commit += " ↺"
        task = (run.prompt_text.strip().splitlines() or [""])[0][:60]
        print(f"{run.id:>5}  {run.started_at:%Y-%m-%d %H:%M}  {run.status.value:<12}  {commit:<9}  {task}")
    return 0


def run_revert(storage, args: argparse.Namespace) -> int:
    run = storage.find_run(args.run)
    if run is None:
        print(_("No run {id} — see `ccc runs CONVERSATION`.").format(id=args.run))
        return 1
    try:
        commit = revert.revert(storage, run)
    except revert.RevertError as error:
        print(error)
        return 1
    print(_("Reverted — commit {commit}.").format(commit=commit[:7]))
    if args.tell:
        revert.tell_claude(storage, run, commit)
        print(_("Claude gets a note in its queue."))
    return 0
