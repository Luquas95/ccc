"""@-mentions of files in a message: typing @ in the message box (or a
task) offers the files of the conversation's folder, narrowed as you
type, and inserts the path the way Claude Code knows it (@src/app.py,
relative to the folder).

The files come from `git ls-files` (tracked + untracked, not ignored)
only where Claude may run commands anyway (gitops), else from walking
the folder — up to a limit, skipping .git, node_modules and the like,
running nothing. Lists are cached for a while; reading and ranking run
in a thread, so a big repository never holds up the UI."""
from __future__ import annotations

import heapq
import os
import threading
import time

# Folders never worth mentioning (walking without git).
SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".tox", ".next", ".nuxt", "dist", "build", "target", ".cache", ".idea", ".gradle",
})
MAX_WALK_FILES = 20_000
CACHE_SECONDS = 30.0
SHOWN = 8


def mention_at(line: str) -> tuple[int, str] | None:
    """The @-mention being typed at the end of `line` (the text before the
    cursor): (column of the @, what follows it), or None. The @ must
    start a word — an e-mail address isn't a mention."""
    start = line.rfind("@")
    if start < 0:
        return None
    query = line[start + 1:]
    if any(c.isspace() for c in query):
        return None
    if start > 0 and not line[start - 1].isspace():
        return None
    return start, query


def walk_files(root: str, limit: int = MAX_WALK_FILES) -> list[str]:
    """Files under root, relative to it, without SKIP_DIRS and hidden
    folders; stops at `limit`."""
    found: list[str] = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        rel = os.path.relpath(folder, root)
        for name in sorted(files):
            found.append(name if rel == "." else f"{rel}/{name}")
            if len(found) >= limit:
                return found
    return found


def rank(files: list[str], query: str, limit: int = SHOWN) -> list[str]:
    """The best `limit` files for query: the text in the file name, then
    anywhere in the path, then its letters in order (fuzzy); shorter
    paths first within each."""
    q = query.lower()
    if not q:
        return heapq.nsmallest(limit, files, key=lambda f: (f.count("/"), len(f), f))
    scored = []
    for f in files:
        low = f.lower()
        at = low.find(q)
        if at >= 0:
            tier = 0 if at > low.rfind("/") else 1
        else:
            letters = iter(low)
            if not all(c in letters for c in q):
                continue
            tier = 2
        scored.append((tier, len(f), f))
    return [f for _tier, _len, f in heapq.nsmallest(limit, scored)]


class FileIndex:
    """Cached file lists per folder (thread-safe)."""

    def __init__(self, ttl: float = CACHE_SECONDS):
        self.ttl = ttl
        self._lists: dict[tuple[str, bool], tuple[float, list[str]]] = {}
        self._lock = threading.Lock()

    def files(self, root: str, use_git: bool) -> list[str]:
        key = (root, use_git)
        with self._lock:
            cached = self._lists.get(key)
        if cached is not None and time.monotonic() - cached[0] < self.ttl:
            return cached[1]
        listed = None
        if use_git:
            from ccc import gitops

            listed = gitops.listed_files(root)
        if listed is None:
            listed = walk_files(root) if os.path.isdir(root) else []
        with self._lock:
            self._lists[key] = (time.monotonic(), listed)
        return listed


INDEX = FileIndex()
