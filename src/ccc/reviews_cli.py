"""`ccc review …` — reviews from the shell and scripts: ask for one (the
daemon runs it), list them, read a report, stop a loop. With --wait the
exit code is the verdict: 0 PASS (or nothing to review), 3 FAIL,
4 PARTIAL, 1 error or stopped."""
from __future__ import annotations

import argparse
import time

from ccc import reviews
from ccc.i18n import _
from ccc.models import ReviewStatus, Verdict
from ccc.routines_cli import conversation_id

WAIT_POLL_SECONDS = 2.0
EXIT_CODES = {Verdict.PASS: 0, Verdict.FAIL: 3, Verdict.PARTIAL: 4}


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("review", help=_("Fresh-context reviews of a conversation's changes"))
    sub = parser.add_subparsers(dest="review_command", required=True)
    start = sub.add_parser("start", help=_("Ask for a review (the daemon runs it when the conversation is idle)"))
    start.add_argument("conversation", help=_("the conversation: its id or name"))
    start.add_argument("instructions", nargs="?", default="", help=_("what to check first (optional)"))
    start.add_argument("--until-pass", action="store_true",
                       help=_("send the findings back and review again after the fix, until PASS"))
    start.add_argument("--rounds", type=int, default=reviews.DEFAULT_ROUNDS,
                       help=_("at most this many rounds with --until-pass (1–12)"))
    start.add_argument("--wait", action="store_true",
                       help=_("wait for the verdict; exit code 0 PASS, 3 FAIL, 4 PARTIAL, 1 error"))
    listing = sub.add_parser("list", help=_("Reviews, newest first"))
    listing.add_argument("conversation", nargs="?", default=None)
    show = sub.add_parser("show", help=_("A review's report"))
    show.add_argument("review", type=int)
    stop = sub.add_parser("stop", help=_("Stop the conversation's review (loop)"))
    stop.add_argument("conversation")


def _line(review) -> str:
    result = review.verdict.value if review.verdict else review.status.value
    rounds = f" {review.round}/{review.max_rounds}" if review.until_pass or review.round > 1 else ""
    when = (review.finished_at or review.created_at).strftime("%Y-%m-%d %H:%M")
    return f"{review.id:>4}  {when}  {result:<8}{rounds}  {review.scope.splitlines()[0][:70] if review.scope else ''}"


def wait(storage, review_id: int, sleep=time.sleep) -> int:
    """Follow a review (and its later rounds) to the end; the exit code."""
    while True:
        review = storage.get_review(review_id)
        loop = [r for r in storage.list_reviews(review.queue_id) if (r.loop_id or r.id) == (review.loop_id or review.id)]
        if not any(r.status in reviews.ACTIVE for r in loop):
            last = loop[0]  # newest round
            print(_line(last))
            if last.status == ReviewStatus.NOTHING:
                return 0
            if last.status == ReviewStatus.DONE and last.verdict is not None:
                return EXIT_CODES[last.verdict]
            return 1
        sleep(WAIT_POLL_SECONDS)


def run(storage, args: argparse.Namespace, sleep=time.sleep) -> int:
    command = args.review_command
    try:
        if command == "start":
            review = reviews.request(storage, conversation_id(storage, args.conversation), args.instructions,
                                     args.until_pass, args.rounds)
            print(_("Review {id} asked for — the daemon runs it as soon as the conversation is idle.").format(
                id=review.id))
            return wait(storage, review.id, sleep) if args.wait else 0
        if command == "list":
            queue_id = conversation_id(storage, args.conversation, include_archived=True) if args.conversation else None
            items = storage.list_reviews(queue_id)
            for review in items:
                print(_line(review))
            if not items:
                print(_("No reviews yet."))
            return 0
        if command == "show":
            review = storage.find_review(args.review)
            if review is None:
                raise ValueError(_("No review {id}.").format(id=args.review))
            print(_line(review))
            print()
            print(review.report or review.error or "")
            return 0
        if command == "stop":
            n = reviews.stop(storage, conversation_id(storage, args.conversation, include_archived=True))
            print(_("Stopped: {n}").format(n=n))
            return 0
    except ValueError as error:
        print(error)
        return 1
    return 2
