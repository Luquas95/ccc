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
import re
import subprocess
from dataclasses import dataclass

from ccc.i18n import _

logger = logging.getLogger(__name__)

SHOW_MAX_CHARS = 200_000


_HARDENING = [
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.fsmonitor=false",
    "-c", "core.untrackedCache=false",
    "-c", "diff.external=",
    "-c", "core.pager=cat",
    "-c", "commit.gpgSign=false",
    "-c", "tag.gpgSign=false",
    "-c", "log.showSignature=false",
    "-c", "gpg.program=/bin/false",
    "-c", "gpg.ssh.program=/bin/false",
    "-c", "gpg.x509.program=/bin/false",
]

# Fail-closed allowlist of repo-local config keys that never make git run
# a program. Anything else (git has many ways to run programs from
# config) blocks the daemon from running further git in that repo.
_SAFE_KEY_PATTERNS = [re.compile(p) for p in (
    r"core\.(repositoryformatversion|filemode|bare|logallrefupdates|ignorecase|precomposeunicode|symlinks|autocrlf|eol|safecrlf|quotepath)",
    r"remote\.[^.]+\.(url|fetch|pushurl|tagopt|prune)",
    r"branch\.[^.]+\.(remote|merge|rebase|pushremote)",
    r"user\.(name|email)",
    r"init\.defaultbranch",
    r"pull\.(rebase|ff)",
    r"push\.(default|autosetupremote)",
    r"fetch\.prune",
    r"extensions\.(objectformat|worktreeconfig)",
)]


def _config_entries(raw: str) -> list[tuple[str, str]]:
    """Parse `git config --list --null`: entries end with NUL, key and value
    are split by the first newline — unambiguous even for multi-line values."""
    entries = []
    for entry in raw.split("\x00"):
        if not entry:
            continue
        key, _sep, value = entry.partition("\n")
        entries.append((key.strip().lower(), value))
    return entries


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
    config_fingerprint: str = ""
    # Set when the repo's config is unsafe for the daemon to run git in.
    blocked: str | None = None


@dataclass
class CommitOutcome:
    commit: str | None
    note: str


def _local_config(cwd: str) -> str | None:
    """The repo-local config (reading runs nothing; --no-includes so include
    lines are seen, not followed). None when it can't be read."""
    result = _git(cwd, "config", "--local", "--list", "--null", "--no-includes")
    return result.stdout if result.returncode == 0 else None


def _config_problem(config: str | None) -> str | None:
    if config is None:
        return _("couldn't read the repo's git config")
    for key, _value in _config_entries(config):
        if not any(p.fullmatch(key) for p in _SAFE_KEY_PATTERNS):
            return _("repo git config has '{key}', which ccc doesn't run git with").format(key=key)
    return None


def snapshot(cwd: str) -> Snapshot | None:
    """State before a task; None when cwd isn't inside a git work tree."""
    try:
        inside = _git(cwd, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.TimeoutExpired):
        return None
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return None
    config = _local_config(cwd)
    problem = _config_problem(config)
    if problem:
        # Checked before `git status`, which can already run clean filters.
        return Snapshot("", False, False, config or "", blocked=problem)
    head = _git(cwd, "rev-parse", "HEAD")
    status = _git(cwd, "status", "--porcelain")
    branch = _git(cwd, "symbolic-ref", "-q", "HEAD")
    return Snapshot(
        head=head.stdout.strip() if head.returncode == 0 else "",
        clean=status.returncode == 0 and status.stdout.strip() == "",
        on_branch=branch.returncode == 0,
        config_fingerprint=config,
    )


def commit_task(cwd: str, before: Snapshot, task_text: str, conversation: str) -> CommitOutcome:
    if before.blocked:
        return CommitOutcome(None, _("not committed: {reason}").format(reason=before.blocked))
    config = _local_config(cwd)
    if config is None or config != before.config_fingerprint:
        return CommitOutcome(None, _("not committed: the repo's git config changed during the task"))
    problem = _config_problem(config)
    if problem:
        return CommitOutcome(None, _("not committed: {reason}").format(reason=problem))
    if not before.clean:
        return CommitOutcome(None, _("not committed: there were uncommitted changes before the task"))
    if not before.on_branch:
        return CommitOutcome(None, _("not committed: detached HEAD"))
    status = _git(cwd, "status", "--porcelain")
    if status.returncode != 0:
        return CommitOutcome(None, _("not committed: git status failed"))
    if status.stdout.strip() == "":
        return CommitOutcome(None, _("no changes"))
    first_line = (task_text.strip().splitlines() or ["task"])[0][:72]
    message = f"ccc: {first_line}\n\nccc-conversation: {conversation}\n"
    added = _git(cwd, "add", "-A")
    committed = _git(cwd, "commit", "-q", "--no-verify", "-m", message) if added.returncode == 0 else added
    if committed.returncode != 0:
        logger.warning("auto-commit failed in %s: %s", cwd, committed.stderr.strip()[:300])
        return CommitOutcome(None, _("not committed: git commit failed"))
    head = _git(cwd, "rev-parse", "HEAD").stdout.strip()
    return CommitOutcome(head, _("committed"))


def show(cwd: str, commit: str) -> str:
    problem = _config_problem(_local_config(cwd))
    if problem:
        return _("Not shown: {reason}.").format(reason=problem)
    result = _git(cwd, "show", "--stat", "--patch", "--no-color", "--no-ext-diff", "--no-textconv", commit)
    text = result.stdout if result.returncode == 0 else result.stderr
    if len(text) > SHOW_MAX_CHARS:
        text = text[:SHOW_MAX_CHARS] + "\n" + _("… (truncated, {n} chars)").format(n=len(text))
    return text
