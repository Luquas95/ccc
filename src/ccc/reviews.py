"""The reviewer: a separate Claude Code run with a clean context that
reads what a conversation changed and ends with one verdict — PASS,
FAIL or PARTIAL. The agent that wrote a patch is a poor judge of it; a
reviewer that never saw its reasoning reads the code as it is.

- The TUI (v) or `ccc review` asks for a review (request()); the daemon
  runs it (tick()) once the conversation is idle and the usage limits
  allow, the same way it runs tasks.
- What's reviewed (scope()): the commits ccc made for the conversation's
  tasks since the last review; else the uncommitted changes in its git
  repository; else the files of the tasks since then. Nothing new: no
  model is called (status NOTHING).
- The reviewer can't change or run anything: only Read, Grep and Glob,
  with dontAsk refusing everything else. ccc gives it the diff itself
  (gitops.review_diff, hardened git). It loads only your user settings —
  none of the project's (no allow rules, hooks or .mcp.json from the
  repo it reviews).
- Its findings can go back to the conversation as a task (apply()); with
  "until it passes" that happens by itself, and once the fix is done the
  next round reviews again — until PASS or the round limit."""
from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from ccc import gitops, i18n
from ccc.i18n import N_, _
from ccc.limits import exhausted_until, retry_time_after_rate_limit
from ccc.notify import CAT_RESULTS
from ccc.models import (
    PromptRun, Queue, QueueItem, QueueStatus, Review, ReviewStatus, RunStatus, Verdict,
)
from ccc.runner import RunResult, classify_output

MODEL_KEY = "review_model"  # "" = the conversation's own model
MODEL_CHOICES = [("", N_("Same as the conversation")), ("opus", "Opus"), ("sonnet", "Sonnet"),
                 ("haiku", "Haiku"), ("fable", "Fable")]
DEFAULT_ROUNDS = 5
MAX_ROUNDS = 12
TOOLS = "Read,Grep,Glob"
# A review never starts sooner than this after a usage-limit answer with
# no reset time.
LIMIT_BACKOFF = timedelta(minutes=15)
TASK_SUMMARY_CHARS = 500
ACTIVE = (ReviewStatus.PENDING, ReviewStatus.RUNNING)

_VERDICT = re.compile(r"VERDICT\**\s*:\s*\**\s*(PASS|FAIL|PARTIAL)\b\**\s*[—–:-]*\s*(.*)", re.IGNORECASE)

# (project_path, prompt, model or None) -> RunResult
ReviewRunFn = Callable[[str, str, "str | None"], Awaitable[RunResult]]


def command(prompt: str, model: str | None) -> list[str]:
    """`claude -p` that can only read: a fresh session that isn't saved,
    without the reviewed project's settings."""
    return ["claude", "-p", prompt, "--output-format", "json", "--no-session-persistence",
            "--tools", TOOLS, "--permission-mode", "dontAsk", "--setting-sources", "user",
            *(["--model", model] if model else [])]


async def execute(project_path: str, prompt: str, model: str | None) -> RunResult:
    proc = await asyncio.create_subprocess_exec(
        *command(prompt, model), cwd=project_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return classify_output(stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"),
                           proc.returncode or 0)


def parse_verdict(text: str) -> tuple[Verdict | None, str]:
    """The last VERDICT line of a report: (verdict, its reason)."""
    found = None
    for line in (text or "").splitlines():
        match = _VERDICT.search(line)
        if match:
            found = match
    if found is None:
        return None, ""
    return Verdict(found.group(1).upper()), found.group(2).strip()


def active(storage, queue_id: int) -> Review | None:
    """A review of the conversation that waits or runs."""
    for review in storage.list_reviews(queue_id):
        if review.status in ACTIVE:
            return review
    return None


def _base_run_id(storage, queue_id: int) -> int:
    """Where a new review starts: after what the last finished one covered."""
    for review in storage.list_reviews(queue_id):
        if review.status in (ReviewStatus.DONE, ReviewStatus.NOTHING):
            return review.last_run_id
    return 0


def request(storage, queue_id: int, instructions: str = "", until_pass: bool = False,
            max_rounds: int = DEFAULT_ROUNDS) -> Review:
    """Ask for a review (the daemon runs it). ValueError when one already
    waits or runs for this conversation."""
    if storage.find_queue(queue_id) is None:
        raise ValueError(_("That conversation doesn't exist."))
    if active(storage, queue_id) is not None:
        raise ValueError(_("A review of this conversation is already waiting or running."))
    rounds = max(1, min(int(max_rounds), MAX_ROUNDS)) if until_pass else 1
    review = storage.add_review(queue_id, instructions.strip(), until_pass, 1, rounds)
    storage.update_review(review.id, base_run_id=_base_run_id(storage, queue_id))
    return storage.get_review(review.id)


def stop(storage, queue_id: int) -> int:
    """Stop the conversation's review loop: a waiting review is dropped, a
    running one finishes without starting another round. Returns how many."""
    stopped = 0
    for review in storage.list_reviews(queue_id):
        if review.status == ReviewStatus.PENDING:
            storage.update_review(review.id, status=ReviewStatus.STOPPED, finished_at=datetime.now())
            stopped += 1
        elif review.status == ReviewStatus.RUNNING and review.until_pass:
            storage.update_review(review.id, until_pass=False)
            stopped += 1
    return stopped


def scope(storage, queue: Queue, review: Review) -> tuple[str, str, int] | None:
    """(what's reviewed — in words for you, what to review — for the
    reviewer, newest run covered); None when there's nothing new."""
    runs = storage.task_runs_after(queue.id, review.base_run_id)
    last = max([r.id for r in runs], default=review.base_run_id)
    commits = [r.git_commit for r in runs if r.git_commit]
    # ccc runs git only where Claude may run commands anyway (see gitops).
    git_allowed = gitops.claude_can_run_commands(queue)
    if commits:
        diff = gitops.review_diff(queue.project_path, commits) if git_allowed else None
        short = ", ".join(c[:12] for c in commits)
        what = f"The commits {short}" + (f":\n\n```diff\n{diff}\n```" if diff else
                                         " (their diff isn't available — read the files the tasks changed).")
        return _("commits {commits}").format(commits=short), what, last
    snapshot = gitops.snapshot(queue.project_path) if git_allowed else None
    if snapshot is not None and not snapshot.blocked and not snapshot.clean:
        diff = gitops.review_diff(queue.project_path, []) or ""
        return (_("uncommitted changes"),
                f"The uncommitted changes in the working tree:\n\n```diff\n{diff}\n```", last)
    if any(r.status == RunStatus.SUCCESS for r in runs):
        return (_("the files of the tasks since the last review"),
                "The files the tasks below changed (there's no git history to diff — find them from the tasks).",
                last)
    return None


def prompt(storage, queue: Queue, review: Review, what: str) -> str:
    tasks = [r for r in storage.task_runs_after(queue.id, review.base_run_id) if r.status == RunStatus.SUCCESS]
    lines = [
        "You are reviewing changes that another Claude Code session made in this repository. You did not "
        "write them: read them fresh and judge the code as it is now, not anyone's description of it. "
        "Do not change any file.",
        "",
        "What to review:",
        what,
    ]
    goal = storage.find_goal(review.goal_id) if review.goal_id else None
    if goal is not None:
        lines += ["", "The session works towards this goal. Judge whether the code now MEETS it — PASS only when "
                  "it fully does, not just when the changes look tidy:", goal.goal]
    elif review.instructions:
        lines += ["", "The user asks you to check this first:", review.instructions]
    if tasks:
        lines += ["", "What the session was asked to do, and what it said it did:"]
        for run in tasks[-10:]:
            said = (run.result_text or "").strip().replace("\n", " ")[:TASK_SUMMARY_CHARS]
            lines.append(f"- task: {run.prompt_text.strip()[:TASK_SUMMARY_CHARS]}")
            if said:
                lines.append(f"  said: {said}")
    if review.round > 1:
        lines += ["", f"This is round {review.round}: earlier findings were sent back and fixed. Check that "
                  "they really are fixed and that nothing that worked before broke."]
    lines += [
        "",
        "Look for bugs, wrong edge cases, missing or weak tests, and callers of changed code that now break. "
        "Be concrete: file:line and what is wrong.",
        "",
        "End your answer with exactly one line, one of:",
        "VERDICT: PASS — what you verified",
        "VERDICT: FAIL — file:line, what is wrong",
        "VERDICT: PARTIAL — what you could not verify and why",
    ]
    if i18n.language() == "cs":
        lines.append("Write the report in Czech; keep the VERDICT line's keyword in English.")
    return "\n".join(lines)


def fix_prompt(review: Review) -> str:
    return _("A fresh reviewer checked your recent changes (verdict {verdict}) and reports:\n\n{report}\n\n"
             "Fix what it found. Where you disagree with a finding, say why instead of changing the code.").format(
        verdict=review.verdict.value if review.verdict else "?", report=review.report.strip())


def apply(storage, review: Review) -> QueueItem:
    """Send the findings back to the conversation as a task."""
    item = storage.add_queue_item(review.queue_id, fix_prompt(review))
    storage.update_review(review.id, fix_item_id=item.id)
    return item


def model_for(storage, queue: Queue) -> str | None:
    chosen = storage.get_setting(MODEL_KEY) or ""
    if chosen:
        return chosen
    flags = queue.launch_flags or []
    return flags[flags.index("--model") + 1] if "--model" in flags[:-1] else None


def ready(storage, queue: Queue) -> bool:
    """The conversation has nothing running or waiting — reviewing code
    that's still changing would judge code that's about to be gone."""
    # A queue working on a task isn't IDLE (RUNNING, waiting for a limit, blocked).
    if queue.status != QueueStatus.IDLE or storage.count_pending_items(queue.id):
        return False
    # An interactive conversation's task is done once pasted; Claude may
    # still be working on it — ask the session itself.
    return not queue.delivery_mode.managed or managed_idle(queue)


def managed_idle(queue: Queue) -> bool:
    """The conversation's interactive Claude Code isn't working (or isn't
    running at all), as `claude agents` reports it."""
    from ccc import managed_sessions
    from ccc.session_discovery import discover_sessions

    if not managed_sessions.is_running(queue.id):
        return True
    pid = managed_sessions.pane_pid(queue.id)
    session = next((s for s in discover_sessions()
                    if (pid is not None and s.pid == pid) or s.session_id == queue.session_id), None)
    return session is None or session.status == "idle"


def _record_run(storage, queue: Queue, review: Review, result: RunResult, started: datetime) -> None:
    """Count the review's tokens like a task's (Analytics, queue detail)."""
    run_id = storage.insert_prompt_run(PromptRun(
        id=0, queue_id=queue.id, queue_item_id=None, prompt_text=_("🔎 review (round {n})").format(n=review.round),
        started_at=started, finished_at=datetime.now(), status=result.status, cost_usd=result.cost_usd,
        input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens, cache_creation_tokens=result.cache_creation_tokens,
        duration_ms=result.duration_ms, num_turns=result.num_turns, result_text=result.result_text,
        error_text=result.error_text, review_id=review.id,
    ))
    for model_name, tokens in result.model_usage.items():
        storage.insert_run_model_usage(run_id, model_name, **tokens)


def _notify(notifier, text: str, review: Review | None = None) -> None:
    # A goal loop's reviews are its rounds: the goal tells how it ended (ccc.goals).
    if notifier is not None and (review is None or review.goal_id is None):
        notifier.notify(text, CAT_RESULTS)


STATUS_LABELS = {
    ReviewStatus.PENDING: N_("waiting"),
    ReviewStatus.RUNNING: N_("reviewing…"),
    ReviewStatus.DONE: N_("done"),
    ReviewStatus.NOTHING: N_("nothing new"),
    ReviewStatus.ERROR: N_("failed"),
    ReviewStatus.STOPPED: N_("stopped"),
}
VERDICT_ICONS = {Verdict.PASS: "✅", Verdict.FAIL: "❌", Verdict.PARTIAL: "⚠️"}


async def run(storage, review: Review, run_fn: ReviewRunFn = execute, notifier=None,
              usage_fn: Callable = None, now: datetime | None = None) -> Review:
    """Run one waiting review if its conversation and the limits allow it."""
    from ccc.orchestrator import usage_reserve
    from ccc.usage_api import get_pro_usage

    now = now or datetime.now()
    queue = storage.find_queue(review.queue_id)
    if queue is None:
        storage.update_review(review.id, status=ReviewStatus.ERROR, error=_("The conversation was deleted."))
        return storage.get_review(review.id)
    if not await asyncio.to_thread(ready, storage, queue):
        return review
    found = scope(storage, queue, review)
    if found is None:
        storage.update_review(review.id, status=ReviewStatus.NOTHING, finished_at=now,
                              last_run_id=review.base_run_id, scope=_("nothing new to review"))
        return storage.get_review(review.id)
    usage = await asyncio.to_thread(usage_fn or get_pro_usage)
    reserve = usage_reserve(storage)
    until = exhausted_until(usage, now, threshold=reserve) if reserve else exhausted_until(usage, now)
    if until is not None:
        storage.update_review(review.id, not_before=until)
        return storage.get_review(review.id)

    label, what, last_run_id = found
    storage.update_review(review.id, status=ReviewStatus.RUNNING, scope=label, last_run_id=last_run_id)
    started = datetime.now()
    result = await run_fn(queue.project_path, prompt(storage, queue, review, what),
                          review.model or model_for(storage, queue))
    _record_run(storage, queue, review, result, started)

    if result.status == RunStatus.RATE_LIMITED:
        retry = retry_time_after_rate_limit(await asyncio.to_thread(usage_fn or get_pro_usage), datetime.now())
        storage.update_review(review.id, status=ReviewStatus.PENDING, not_before=retry or now + LIMIT_BACKOFF)
        return storage.get_review(review.id)
    if result.status != RunStatus.SUCCESS:
        storage.update_review(review.id, status=ReviewStatus.ERROR, error=(result.error_text or "")[:2000],
                              finished_at=datetime.now())
        _notify(notifier, _("🔎 {name}: the review failed — {error}").format(
            name=queue.name, error=(result.error_text or "")[:200]), review)
        return storage.get_review(review.id)

    report = (result.result_text or "").strip()
    verdict, reason = parse_verdict(report)
    if verdict is None:
        storage.update_review(review.id, status=ReviewStatus.ERROR, report=report, finished_at=datetime.now(),
                              error=_("The reviewer gave no VERDICT line."))
        _notify(notifier, _("🔎 {name}: the reviewer gave no verdict.").format(name=queue.name), review)
        return storage.get_review(review.id)
    storage.update_review(review.id, status=ReviewStatus.DONE, verdict=verdict, report=report,
                          finished_at=datetime.now())
    review = storage.get_review(review.id)
    text = _("🔎 {name}: review {verdict} — {reason}").format(name=queue.name, verdict=verdict.value, reason=reason)
    if verdict != Verdict.PASS and review.until_pass:
        if review.round < review.max_rounds:
            apply(storage, review)
            storage.add_review(queue.id, review.instructions, True, review.round + 1, review.max_rounds,
                               review.loop_id or review.id)
            nxt = storage.list_reviews(queue.id, ReviewStatus.PENDING)[0]
            storage.update_review(nxt.id, base_run_id=_loop_base(storage, review))
            text += "\n" + _("Findings sent back; round {n} of {max} reviews again after the fix.").format(
                n=review.round + 1, max=review.max_rounds)
        else:
            text += "\n" + _("Round limit ({max}) reached — the loop stops.").format(max=review.max_rounds)
    _notify(notifier, text, review)
    return storage.get_review(review.id)


def _loop_base(storage, review: Review) -> int:
    """A later round re-checks the whole loop's work: from where round 1 began."""
    first = storage.find_review(review.loop_id) if review.loop_id else review
    return first.base_run_id if first else review.base_run_id


async def tick(storage, run_fn: ReviewRunFn = execute, notifier=None, usage_fn: Callable = None,
               now: datetime | None = None) -> list[Review]:
    """Run the reviews that can run now (one per conversation, in order)."""
    now = now or datetime.now()
    done = []
    for review in reversed(storage.list_reviews(status=ReviewStatus.PENDING)):
        if review.not_before is not None and review.not_before > now:
            continue
        after = await run(storage, review, run_fn, notifier, usage_fn, now)
        if after.status != ReviewStatus.PENDING:
            done.append(after)
    return done

