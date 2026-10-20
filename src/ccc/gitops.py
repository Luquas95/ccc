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
from pathlib import Path

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


def revert_commit(cwd: str, commit: str, conversation: str) -> CommitOutcome:
    """Undo one of ccc's task commits with a new commit (git revert). Only
    in a clean work tree on a branch, for a commit in its history; a
    revert that conflicts with later changes is abandoned (nothing
    changes). CommitOutcome.commit is the revert commit, or None with why."""
    if not _COMMIT.match(commit or ""):
        return CommitOutcome(None, _("not reverted: that isn't a commit"))
    before = snapshot(cwd)
    if before is None:
        return CommitOutcome(None, _("not reverted: not a git repository"))
    if before.blocked:
        return CommitOutcome(None, _("not reverted: {reason}").format(reason=before.blocked))
    if not before.clean:
        return CommitOutcome(None, _("not reverted: there are uncommitted changes — commit or stash them first"))
    if not before.on_branch:
        return CommitOutcome(None, _("not reverted: detached HEAD"))
    if _git(cwd, "merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        return CommitOutcome(None, _("not reverted: the commit isn't in this branch's history"))
    subject = _git(cwd, "log", "-1", "--format=%s", commit).stdout.strip()
    reverted = _git(cwd, "revert", "--no-edit", "--no-commit", commit)
    if reverted.returncode != 0:
        _git(cwd, "revert", "--abort")
        return CommitOutcome(None, _("not reverted: it conflicts with later changes — nothing was changed"))
    if _git(cwd, "status", "--porcelain").stdout.strip() == "":
        return CommitOutcome(None, _("not reverted: its changes are already gone"))
    message = f"ccc: revert {commit[:7]} ({subject[:60]})\n\nccc-conversation: {conversation}\nccc-reverts: {commit}\n"
    committed = _git(cwd, "commit", "-q", "--no-verify", "-m", message)
    if committed.returncode != 0:
        _git(cwd, "revert", "--abort")
        return CommitOutcome(None, _("not reverted: git commit failed"))
    return CommitOutcome(_git(cwd, "rev-parse", "HEAD").stdout.strip(), _("reverted"))


WORKTREES_DIR = Path(".claude") / "worktrees"  # where Claude Code keeps its own (claude --worktree)
_SLUG = re.compile(r"[^a-z0-9._-]+")


def work_tree_root(path: str) -> str | None:
    """The top folder of the git work tree `path` is in (a worktree is its
    own); None outside git."""
    try:
        result = _git(path, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def create_worktree(path: str, name: str) -> str:
    """A new git worktree for a conversation: <repo>/.claude/worktrees/<name>
    on a new branch worktree-<name> from HEAD — where `claude --worktree
    <name>` keeps its own, so Claude Code can open it too. The folder is
    left out of the main checkout's `git status` (.git/info/exclude).
    Returns its path; ValueError with a message for the user."""
    top = work_tree_root(path)
    if top is None:
        raise ValueError(_("A worktree needs a git repository — {path} isn't in one.").format(path=path))
    problem = _config_problem(_local_config(top))
    if problem:
        raise ValueError(_("No worktree: {reason}.").format(reason=problem))
    base = _SLUG.sub("-", name.lower()).strip("-.")[:40] or "conversation"
    slug, n = base, 1
    while (Path(top) / WORKTREES_DIR / slug).exists() or _git(
            top, "rev-parse", "--verify", "--quiet", f"refs/heads/worktree-{slug}").returncode == 0:
        n += 1
        slug = f"{base}-{n}"
    exclude = _git(top, "rev-parse", "--git-path", "info/exclude").stdout.strip()
    if exclude:
        exclude_path = Path(exclude) if Path(exclude).is_absolute() else Path(top) / exclude
        lines = exclude_path.read_text().splitlines() if exclude_path.exists() else []
        if f"/{WORKTREES_DIR.as_posix()}/" not in lines:
            exclude_path.parent.mkdir(parents=True, exist_ok=True)
            with exclude_path.open("a") as handle:
                handle.write(f"/{WORKTREES_DIR.as_posix()}/\n")
    target = Path(top) / WORKTREES_DIR / slug
    added = _git(top, "worktree", "add", "-q", "-b", f"worktree-{slug}", str(target), "HEAD")
    if added.returncode != 0:
        raise ValueError(_("No worktree: {error}").format(error=added.stderr.strip()[:300]))
    return str(target)


REVIEW_DIFF_MAX_CHARS = 60_000
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")


def review_diff(cwd: str, commits: list[str]) -> str | None:
    """What a reviewer reads (ccc.reviews): the commits, or with none the
    uncommitted changes and the names of new files. None when cwd isn't a
    git work tree or its config isn't safe to run git with."""
    try:
        inside = _git(cwd, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.TimeoutExpired):
        return None
    if inside.returncode != 0 or inside.stdout.strip() != "true" or _config_problem(_local_config(cwd)):
        return None
    commits = [c for c in commits if _COMMIT.match(c)]
    if commits:
        result = _git(cwd, "show", "--stat", "--patch", "--no-color", "--no-ext-diff", "--no-textconv", *commits)
        text = result.stdout if result.returncode == 0 else ""
    else:
        diff = _git(cwd, "diff", "--no-color", "--no-ext-diff", "--no-textconv", "HEAD")
        new = _git(cwd, "ls-files", "--others", "--exclude-standard")
        text = diff.stdout if diff.returncode == 0 else ""
        if new.returncode == 0 and new.stdout.strip():
            text += "\nNew files (read them whole):\n" + new.stdout
    if len(text) > REVIEW_DIFF_MAX_CHARS:
        text = text[:REVIEW_DIFF_MAX_CHARS] + f"\n… (cut at {REVIEW_DIFF_MAX_CHARS} characters; read the files for the rest)"
    return text


def show(cwd: str, commit: str) -> str:
    problem = _config_problem(_local_config(cwd))
    if problem:
        return _("Not shown: {reason}.").format(reason=problem)
    result = _git(cwd, "show", "--stat", "--patch", "--no-color", "--no-ext-diff", "--no-textconv", commit)
    text = result.stdout if result.returncode == 0 else result.stderr
    if len(text) > SHOW_MAX_CHARS:
        text = text[:SHOW_MAX_CHARS] + "\n" + _("… (truncated, {n} chars)").format(n=len(text))
    return text
