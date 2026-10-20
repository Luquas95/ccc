"""Several conversations in one folder. Two of them editing the same work
tree at once get in each other's way — worse, ccc's commit after one
task would sweep in the other's half-written changes. So:

- headless tasks of conversations sharing a git work tree take turns
  (the orchestrator waits while a neighbour runs one);
- ccc doesn't commit while another conversation works in the same tree;
- Conversations says which others share the folder, and a conversation
  can get its own git worktree when it starts (gitops.create_worktree).

A git worktree is its own work tree, so conversations in different
worktrees of one repository don't share anything here. ccc asks git
which work tree a folder is in only for conversations where Claude may
run commands anyway (see gitops); for the others it's their folder."""
from __future__ import annotations

import os
import time

from ccc import gitops
from ccc.models import Queue, QueueStatus

CACHE_SECONDS = 60.0
_roots: dict[str, tuple[float, str]] = {}


def work_tree(queue: Queue) -> str:
    """The git work tree the conversation works in (its folder outside git,
    or where ccc doesn't run git for it)."""
    path = queue.project_path
    if not gitops.claude_can_run_commands(queue):
        return os.path.realpath(path)
    now = time.monotonic()
    cached = _roots.get(path)
    if cached is not None and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    root = gitops.work_tree_root(path) or os.path.realpath(path)
    _roots[path] = (now, root)
    return root


def neighbours(storage, queue: Queue) -> list[Queue]:
    """The other active conversations in the same work tree."""
    mine = work_tree(queue)
    return [q for q in storage.list_queues()
            if q.id != queue.id and not q.archived and work_tree(q) == mine]


def running_neighbour(storage, queue: Queue) -> Queue | None:
    """A neighbour running a task right now (headless: the whole task)."""
    return next((q for q in neighbours(storage, queue) if q.status == QueueStatus.RUNNING), None)


def busy_neighbour(storage, queue: Queue) -> Queue | None:
    """A neighbour working: running a task, or an interactive Claude Code
    busy with something (also something typed into it by hand)."""
    from ccc.reviews import managed_idle

    for other in neighbours(storage, queue):
        if other.status == QueueStatus.RUNNING:
            return other
        if other.delivery_mode.managed and not managed_idle(other):
            return other
    return None
