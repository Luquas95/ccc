"""Groups in the list of Conversations / Archive: conversations under
foldable headings (▾ shop (3) · ? 1).

A conversation is in the group you put it in (m; kept in the
conversation_groups table), else — grouping "by project", the default —
in its project's: the git repository it works in (a worktree under its
repository), or its folder outside git. Grouping "own groups only" puts
the rest under "No group", and without any own group the list stays flat.

The repository is found by reading the .git entries on the way up — no
git process, so this works for every conversation (ccc runs git only
where Claude may run commands, see gitops). Which headings are folded is
the collapsed_groups setting (JSON list of group keys)."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from ccc.i18n import _
from ccc.models import Queue

MODE_KEY = "conversation_groups"
COLLAPSED_KEY = "collapsed_groups"
BY_PROJECT, OWN_ONLY = "project", "own"
NO_GROUP = "none"
CACHE_SECONDS = 60.0
_projects: dict[str, tuple[float, str]] = {}


@dataclass(frozen=True)
class Group:
    key: str  # "own:<name>", "project:<path>" or NO_GROUP
    title: str

    @property
    def own(self) -> str | None:
        """The name of an own group (None for a project / no group)."""
        return self.key.removeprefix("own:") if self.key.startswith("own:") else None


def mode(storage) -> str:
    return OWN_ONLY if storage.get_setting(MODE_KEY) == OWN_ONLY else BY_PROJECT


def project_root(path: str) -> str:
    """The repository `path` is in (a worktree's main repository), else
    the folder itself."""
    now = time.monotonic()
    cached = _projects.get(path)
    if cached is not None and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    root = _repository(os.path.realpath(path)) or os.path.realpath(path)
    _projects[path] = (now, root)
    return root


def _repository(folder: str) -> str | None:
    current = folder
    while True:
        dot_git = os.path.join(current, ".git")
        if os.path.isdir(dot_git):
            return current
        if os.path.isfile(dot_git):
            return _worktree_repository(dot_git) or current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _worktree_repository(dot_git: str) -> str | None:
    """A worktree's .git file says "gitdir: <repo>/.git/worktrees/<name>";
    its commondir leads to the repository's .git."""
    try:
        with open(dot_git, encoding="utf-8") as f:
            line = f.readline().strip()
        if not line.startswith("gitdir:"):
            return None
        gitdir = os.path.join(os.path.dirname(dot_git), line.removeprefix("gitdir:").strip())
        with open(os.path.join(gitdir, "commondir"), encoding="utf-8") as f:
            common = os.path.join(gitdir, f.readline().strip())
    except OSError:
        return None
    return os.path.dirname(os.path.realpath(common))


def grouped(queues: list[Queue], own: dict[int, str], grouping: str) -> list[tuple[Group | None, list[Queue]]]:
    """The queues under their groups, in list order: own groups, then
    projects (both by name), then No group. One (None, queues) entry when
    there's nothing to group by (own groups only, none in use)."""
    members: dict[str, list[Queue]] = {}
    titles: dict[str, str] = {}
    for q in queues:
        name = own.get(q.id)
        if name:
            key, title = f"own:{name}", name
        elif grouping == BY_PROJECT:
            root = project_root(q.project_path)
            key, title = f"project:{root}", os.path.basename(root) or root
        else:
            key, title = NO_GROUP, _("No group")
        members.setdefault(key, []).append(q)
        titles[key] = title
    if not members or set(members) == {NO_GROUP}:
        return [(None, queues)]
    _disambiguate(titles)

    def order(key: str) -> tuple:
        kind = 0 if key.startswith("own:") else 1 if key.startswith("project:") else 2
        return kind, titles[key].casefold(), key

    return [(Group(key, titles[key]), members[key]) for key in sorted(members, key=order)]


def _disambiguate(titles: dict[str, str]) -> None:
    """Two projects called "app": show "work/app" and "home/app"."""
    seen: dict[str, list[str]] = {}
    for key, title in titles.items():
        if key.startswith("project:"):
            seen.setdefault(title, []).append(key)
    for keys in seen.values():
        if len(keys) > 1:
            for key in keys:
                path = key.removeprefix("project:")
                titles[key] = os.path.join(os.path.basename(os.path.dirname(path)), os.path.basename(path))


def collapsed(storage) -> set[str]:
    try:
        return set(json.loads(storage.get_setting(COLLAPSED_KEY) or "[]"))
    except (ValueError, TypeError):
        return set()


def set_collapsed(storage, key: str, value: bool) -> None:
    keys = collapsed(storage)
    keys = keys | {key} if value else keys - {key}
    storage.set_setting(COLLAPSED_KEY, json.dumps(sorted(keys)))


def rename(storage, old: str, new: str) -> None:
    """Rename an own group; folded stays folded (into an existing group:
    they merge)."""
    storage.rename_conversation_group(old, new)
    if f"own:{old}" in collapsed(storage):
        set_collapsed(storage, f"own:{old}", False)
        set_collapsed(storage, f"own:{new}", True)


def delete(storage, name: str) -> None:
    """Delete an own group: its conversations go back to their project's
    group (or No group)."""
    storage.delete_conversation_group(name)
    set_collapsed(storage, f"own:{name}", False)
