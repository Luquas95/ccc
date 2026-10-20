"""The goal loop: say once what done looks like, and ccc keeps the
conversation working in rounds until an independent reviewer agrees.

A round: the conversation works on a task (the goal, then the
reviewer's reason) → ccc runs the check command if there is one (e.g.
`pytest -q`; a failing check fails the round without a review) → a
fresh reviewer (ccc.reviews) judges the repository against the goal.
PASS ends it. Otherwise the reason becomes the next round's task.

When progress stalls, each round changes one thing: from round 3 the
reviewer runs on a stronger model (maybe it's the one getting it wrong),
from round 4 the coder too (headless conversations — an interactive one
keeps its model), and round 5 tells it to stop patching and rethink.
It stops on PASS, on the same failure twice in a row (stuck), at the
round limit, or when you stop it.

The daemon runs it (tick(), every few seconds); the TUI (g) and
`ccc goal` start and stop it."""
from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime

from ccc import gitops, reviews
from ccc.i18n import N_, _
from ccc.models import Goal, GoalPhase, GoalStatus, ItemStatus, ReviewStatus, Verdict

DEFAULT_ROUNDS = 5
MAX_ROUNDS = 20
STRONG_MODEL = "opus"
REVIEWER_ESCALATES_AT = 3
CODER_ESCALATES_AT = 4
RETHINK_AT = 5
CHECK_TIMEOUT_SECONDS = 15 * 60
CHECK_OUTPUT_CHARS = 3000
FINISHED_ICONS = {GoalStatus.PASSED: "✅", GoalStatus.STUCK: "⛔", GoalStatus.LIMIT: "⛔",
                  GoalStatus.ERROR: "✖", GoalStatus.STOPPED: "■"}


def active(storage, queue_id: int) -> Goal | None:
    for goal in storage.list_goals(queue_id):
        if goal.status == GoalStatus.RUNNING:
            return goal
    return None


def first_prompt(goal: Goal) -> str:
    return _("Work on this goal until it is met:\n\n{goal}\n\nWhen you're done, say briefly what you changed. "
             "A separate reviewer will then check the code against the goal.").format(goal=goal.goal)


def next_prompt(goal: Goal, reason: str) -> str:
    text = _("The goal isn't met yet (round {n} of {max}):\n\n{goal}\n\nWhat the last round found:\n\n{reason}\n\n"
             "Continue towards the goal.").format(n=goal.round, max=goal.max_rounds, goal=goal.goal, reason=reason)
    if goal.round >= RETHINK_AT:
        text += "\n\n" + _("Several rounds haven't got there. Stop patching: step back, rethink the approach and say "
                           "what you'll do differently before you change code.")
    return text


def start(storage, queue_id: int, goal: str, check_command: str = "", max_rounds: int = DEFAULT_ROUNDS) -> Goal:
    """Start a goal loop: its first task goes into the conversation's queue.
    ValueError for an empty goal or when a goal / review already runs."""
    goal = goal.strip()
    if not goal:
        raise ValueError(_("Describe the goal — specific enough to check, e.g. “expired tokens are rejected, "
                           "with a test”."))
    if storage.find_queue(queue_id) is None:
        raise ValueError(_("That conversation doesn't exist."))
    if active(storage, queue_id) is not None:
        raise ValueError(_("A goal is already running in this conversation."))
    if reviews.active(storage, queue_id) is not None:
        raise ValueError(_("A review of this conversation is already waiting or running."))
    rounds = max(1, min(int(max_rounds), MAX_ROUNDS))
    created = storage.add_goal(queue_id, goal, check_command.strip(), rounds, storage.last_run_id(queue_id))
    item = storage.add_queue_item(queue_id, first_prompt(created))
    storage.update_goal(created.id, item_id=item.id)
    return storage.get_goal(created.id)


def stop(storage, queue_id: int) -> bool:
    """Stop the conversation's goal: its waiting task is skipped, its
    waiting review dropped; a task already running finishes."""
    goal = active(storage, queue_id)
    if goal is None:
        return False
    item = storage.get_item(goal.item_id) if goal.item_id else None
    if item is not None and item.status == ItemStatus.PENDING:
        storage.skip_item(item.id)
    review = storage.find_review(goal.review_id) if goal.review_id else None
    if review is not None and review.status == ReviewStatus.PENDING:
        storage.update_review(review.id, status=ReviewStatus.STOPPED, finished_at=datetime.now())
    _finish(storage, goal, GoalStatus.STOPPED, _("stopped by you"))
    return True


def _finish(storage, goal: Goal, status: GoalStatus, reason: str, notifier=None) -> Goal:
    storage.update_goal(goal.id, status=status, last_reason=reason, finished_at=datetime.now())
    goal = storage.get_goal(goal.id)
    if notifier is not None and status != GoalStatus.STOPPED:
        queue = storage.find_queue(goal.queue_id)
        notifier.notify(_("{icon} {name}: goal {status} after {n} round(s) — {reason}").format(
            icon=FINISHED_ICONS[status], name=queue.name if queue else "?", status=_(STATUS_LABELS[status]),
            n=goal.round, reason=reason[:300]))
    return goal


STATUS_LABELS = {
    GoalStatus.RUNNING: N_("running"),
    GoalStatus.PASSED: N_("met"),
    GoalStatus.STUCK: N_("stuck"),
    GoalStatus.LIMIT: N_("out of rounds"),
    GoalStatus.STOPPED: N_("stopped"),
    GoalStatus.ERROR: N_("failed"),
}


def _next_round(storage, goal: Goal, reason: str, details: str = "", notifier=None) -> Goal:
    """The round didn't pass: stuck, out of rounds, or one more round.
    `reason` is what's compared with the last round (the verdict's
    reason, a check's output); `details` what the coder gets (the full
    report), when there's more."""
    reason = reason.strip() or _("(no reason given)")
    if goal.last_reason and reason == goal.last_reason:
        return _finish(storage, goal, GoalStatus.STUCK, _("the same failure twice: {reason}").format(reason=reason),
                       notifier)
    if goal.round >= goal.max_rounds:
        return _finish(storage, goal, GoalStatus.LIMIT, reason, notifier)
    storage.update_goal(goal.id, round=goal.round + 1, last_reason=reason, phase=GoalPhase.CODING, review_id=None)
    goal = storage.get_goal(goal.id)
    queue = storage.get_queue(goal.queue_id)
    model = STRONG_MODEL if goal.round >= CODER_ESCALATES_AT and not queue.delivery_mode.managed else None
    item = storage.add_queue_item(goal.queue_id, next_prompt(goal, details.strip() or reason), model=model)
    storage.update_goal(goal.id, item_id=item.id)
    return storage.get_goal(goal.id)


def run_check(command: str, cwd: str) -> tuple[bool, str]:
    """Run the goal's check command in the project: (passed, the end of
    its output). It's a command line the user wrote for this goal (like a
    CI step: `pytest -q && ruff check .`), hence the shell; advance() runs
    it only where Claude may run any command anyway."""
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True,
                                timeout=CHECK_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return False, _("timed out after {n} min").format(n=CHECK_TIMEOUT_SECONDS // 60)
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output[-CHECK_OUTPUT_CHARS:]


async def advance(storage, goal: Goal, notifier=None, check_fn=run_check) -> Goal:
    """Move one goal on as far as it can go now."""
    queue = storage.find_queue(goal.queue_id)
    if queue is None:
        return _finish(storage, goal, GoalStatus.ERROR, _("the conversation was deleted"))

    if goal.phase == GoalPhase.CODING:
        item = storage.get_item(goal.item_id) if goal.item_id else None
        if item is None or item.status == ItemStatus.SKIPPED:
            return _finish(storage, goal, GoalStatus.ERROR, _("its task was removed from the queue"), notifier)
        if item.status == ItemStatus.FAILED:
            return _finish(storage, goal, GoalStatus.ERROR, _("its task failed: {error}").format(
                error=queue.last_error or "?"), notifier)
        if item.status != ItemStatus.DONE or not await asyncio.to_thread(reviews.ready, storage, queue):
            return goal
        storage.update_goal(goal.id, phase=GoalPhase.CHECKING)
        goal = storage.get_goal(goal.id)

    if goal.phase == GoalPhase.CHECKING:
        # ccc runs the command only where Claude may run commands anyway.
        if goal.check_command and gitops.claude_can_run_commands(queue):
            passed, output = await asyncio.to_thread(check_fn, goal.check_command, queue.project_path)
            if not passed:
                return _next_round(storage, goal, _("The check `{command}` failed:\n{output}").format(
                    command=goal.check_command, output=output), notifier=notifier)
        model = STRONG_MODEL if goal.round >= REVIEWER_ESCALATES_AT else None
        review = storage.add_review(queue.id, goal.goal, round=goal.round, max_rounds=goal.max_rounds,
                                    goal_id=goal.id, model=model, base_run_id=goal.base_run_id)
        storage.update_goal(goal.id, phase=GoalPhase.REVIEWING, review_id=review.id)
        return storage.get_goal(goal.id)

    review = storage.find_review(goal.review_id) if goal.review_id else None
    if review is None or review.status == ReviewStatus.STOPPED:
        return _finish(storage, goal, GoalStatus.ERROR, _("its review is gone"), notifier)
    if review.status in reviews.ACTIVE:
        return goal
    if review.status == ReviewStatus.ERROR:
        return _finish(storage, goal, GoalStatus.ERROR, review.error or _("the review failed"), notifier)
    if review.status == ReviewStatus.NOTHING:
        return _next_round(storage, goal, _("Nothing has changed since the goal started."), notifier=notifier)
    _verdict, reason = reviews.parse_verdict(review.report)
    if review.verdict == Verdict.PASS:
        return _finish(storage, goal, GoalStatus.PASSED, reason, notifier)
    return _next_round(storage, goal, f"{review.verdict.value}: {reason}", review.report, notifier)


async def tick(storage, notifier=None, check_fn=run_check) -> list[Goal]:
    """Advance every running goal; returns the ones that finished."""
    finished = []
    for goal in storage.list_goals(status=GoalStatus.RUNNING):
        after = await advance(storage, goal, notifier, check_fn)
        if after.status != GoalStatus.RUNNING:
            finished.append(after)
    return finished
