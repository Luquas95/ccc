"""`ccc ask FROM TO "question"` (one conversation asks another; with
--wait it prints the answer) and `ccc asks [CONVERSATION]` (the
questions, newest first)."""
from __future__ import annotations

import argparse
import time

from ccc import asks
from ccc.i18n import _
from ccc.models import AskStatus
from ccc.routines_cli import conversation_id

WAIT_POLL_SECONDS = 5.0


def add_parser(subparsers) -> None:
    ask = subparsers.add_parser("ask", help=_("One conversation asks another a question"))
    ask.add_argument("conversation", help=_("the asking conversation: its id or name"))
    ask.add_argument("to", help=_("the conversation to ask: its id or name"))
    ask.add_argument("question")
    ask.add_argument("--no-deliver", action="store_true",
                     help=_("don't pass the answer into the asking conversation"))
    ask.add_argument("--wait", action="store_true", help=_("wait for the answer and print it"))
    listing = subparsers.add_parser("asks", help=_("Questions between conversations, newest first"))
    listing.add_argument("conversation", nargs="?", default=None)


def run_ask(storage, args: argparse.Namespace, sleep=time.sleep) -> int:
    try:
        found = asks.ask(storage, conversation_id(storage, args.conversation), args.to, args.question,
                         deliver=not args.no_deliver)
    except ValueError as error:
        print(error)
        return 1
    print(_("Question {id} asked.").format(id=found.id))
    if not args.wait:
        return 0
    while (found := storage.get_ask(found.id)).status == AskStatus.ASKED:
        sleep(WAIT_POLL_SECONDS)
    print(found.answer or found.error or found.status.value)
    return 0 if found.status == AskStatus.ANSWERED else 1


def run_asks(storage, args: argparse.Namespace) -> int:
    try:
        queue_id = conversation_id(storage, args.conversation, include_archived=True) if args.conversation else None
    except ValueError as error:
        print(error)
        return 1
    names = {q.id: q.name for q in storage.list_queues()}
    items = storage.list_asks(queue_id)
    for a in items:
        who = "🤖" if a.by_agent else " "
        print(f"{a.id:>4}  {a.created_at:%Y-%m-%d %H:%M}  {who} {names.get(a.from_queue_id, '?')} → "
              f"{names.get(a.to_queue_id, '?')}  {a.status.value:<9}  {a.question.splitlines()[0][:60]}")
    if not items:
        print(_("No questions yet."))
    return 0
