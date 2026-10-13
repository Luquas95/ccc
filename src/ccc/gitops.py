"""Git around a headless task: note the state before it, commit what
Claude changed after it, show a commit. Conservative on purpose — never
commits work that was already uncommitted before the task (that's the
user's), nor on a detached HEAD.

Security: the daemon runs git outside Claude's permission mode, in a repo
Claude may have just edited. A conversation limited to editing files
could plant .git/hooks/pre-commit or core.fsmonitor and have ccc execute
it. So (1) the orchestrator only uses this module for conversations that
may run commands anyway (claude_can_run_commands), and (2) every git call
here disables hooks, fsmonitor, external diff/textconv and the pager."""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SHOW_MAX_CHARS = 200_000


_HARDENING = [
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.fsmonitor=false",
    "-c", "core.untrackedCache=false",
    "-c", "diff.external=",
    "-c", "core.pager=cat",
]


def _git(cwd: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *_HARDENING, "-C", cwd, *args],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"},
    )


def claude_can_run_commands(queue) -> bool:
    """True when the conversation's own permission mode already lets
    Claude run arbitrary commands, so ccc running git there grants
    nothing new. Legacy queues (no launch flags) ran with
    --dangerously-skip-permissions."""
    flags = queue.launch_flags
    if flags is None or "--dangerously-skip-permissions" in flags:
        return True
    return any(a == "--permission-mode" and b == "bypassPermissions" for a, b in zip(flags, flags[1:]))


@dataclass
class Snapshot:
    head: str
    clean: bool
    on_branch: bool


@dataclass
class CommitOutcome:
    commit: str | None
    note: str


def snapshot(cwd: str) -> Snapshot | None:
    """State before a task; None when cwd isn't inside a git work tree."""
    try:
        inside = _git(cwd, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.TimeoutExpired):
        return None
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return None
    head = _git(cwd, "rev-parse", "HEAD")
    status = _git(cwd, "status", "--porcelain")
    branch = _git(cwd, "symbolic-ref", "-q", "HEAD")
    return Snapshot(
        head=head.stdout.strip() if head.returncode == 0 else "",
        clean=status.returncode == 0 and status.stdout.strip() == "",
        on_branch=branch.returncode == 0,
    )


def commit_task(cwd: str, before: Snapshot, task_text: str, conversation: str) -> CommitOutcome:
    if not before.clean:
        return CommitOutcome(None, "not committed: there were uncommitted changes before the task")
    if not before.on_branch:
        return CommitOutcome(None, "not committed: detached HEAD")
    status = _git(cwd, "status", "--porcelain")
    if status.returncode != 0:
        return CommitOutcome(None, "not committed: git status failed")
    if status.stdout.strip() == "":
        return CommitOutcome(None, "no changes")
    first_line = (task_text.strip().splitlines() or ["task"])[0][:72]
    message = f"ccc: {first_line}\n\nccc-conversation: {conversation}\n"
    added = _git(cwd, "add", "-A")
    committed = _git(cwd, "commit", "-q", "--no-verify", "-m", message) if added.returncode == 0 else added
    if committed.returncode != 0:
        logger.warning("auto-commit failed in %s: %s", cwd, committed.stderr.strip()[:300])
        return CommitOutcome(None, "not committed: git commit failed")
    head = _git(cwd, "rev-parse", "HEAD").stdout.strip()
    return CommitOutcome(head, "committed")


def show(cwd: str, commit: str) -> str:
    result = _git(cwd, "show", "--stat", "--patch", "--no-color", "--no-ext-diff", "--no-textconv", commit)
    text = result.stdout if result.returncode == 0 else result.stderr
    if len(text) > SHOW_MAX_CHARS:
        text = text[:SHOW_MAX_CHARS] + f"\n… (truncated, {len(text)} chars)"
    return text
