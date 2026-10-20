"""Your own review of a run's commit: comments on lines of its diff, sent
back to the conversation as one prompt (like inline comments on a pull
request). parse() splits `git show` output into lines that know their
file and line number; prompt() turns the comments into the text queued
for Claude."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ccc.i18n import _

HEADER, META, HUNK, ADDED, REMOVED, CONTEXT = "header", "meta", "hunk", "added", "removed", "context"
_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
QUOTE_MAX_CHARS = 200


@dataclass(frozen=True)
class DiffLine:
    text: str
    kind: str
    path: str | None = None  # the file it belongs to (the new name)
    old_line: int | None = None  # line number before the change (removed, context)
    new_line: int | None = None  # line number after it (added, context)

    @property
    def commentable(self) -> bool:
        return self.path is not None and self.kind in (ADDED, REMOVED, CONTEXT, HUNK)


@dataclass
class Comment:
    line: DiffLine
    text: str

    @property
    def where(self) -> str:
        if self.line.kind == REMOVED:
            return _("{path}, removed line {n}").format(path=self.line.path, n=self.line.old_line)
        if self.line.new_line is None:
            return self.line.path or ""
        return f"{self.line.path}:{self.line.new_line}"


def _path(header: str) -> str | None:
    target = header[4:].strip()
    if target == "/dev/null":
        return None
    return target[2:] if target.startswith(("a/", "b/")) else target


def parse(text: str) -> list[DiffLine]:
    lines: list[DiffLine] = []
    path: str | None = None
    old = new = 0
    in_hunk = False
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            path, in_hunk = None, False
            lines.append(DiffLine(raw, META))
        elif not in_hunk and raw.startswith("--- "):
            path = _path(raw)
            lines.append(DiffLine(raw, META))
        elif not in_hunk and raw.startswith("+++ "):
            path = _path(raw) or path  # a deleted file keeps its old name
            lines.append(DiffLine(raw, META))
        elif (match := _HUNK.match(raw)) and path is not None:
            old, new, in_hunk = int(match.group(1)), int(match.group(2)), True
            lines.append(DiffLine(raw, HUNK, path, new_line=new if new else None))
        elif in_hunk and raw.startswith("+"):
            lines.append(DiffLine(raw, ADDED, path, new_line=new))
            new += 1
        elif in_hunk and raw.startswith("-"):
            lines.append(DiffLine(raw, REMOVED, path, old_line=old))
            old += 1
        elif in_hunk and raw.startswith(" "):
            lines.append(DiffLine(raw, CONTEXT, path, old_line=old, new_line=new))
            old += 1
            new += 1
        else:  # commit header, stat, "\ No newline at end of file", index/mode lines
            if not raw.startswith("\\"):
                in_hunk = False
            lines.append(DiffLine(raw, META if path or raw.startswith(("index ", "new ", "deleted ")) else HEADER))
    return lines


def prompt(commit: str, task: str, comments: list[Comment]) -> str:
    parts = [_("I reviewed the changes of your commit {commit} (task “{task}”) and left comments on lines of the "
               "diff. Address each one — change the code, or say why you'd keep it — then sum up what you did.")
             .format(commit=commit[:7], task=task)]
    for n, comment in enumerate(comments, 1):
        code = comment.line.text[:QUOTE_MAX_CHARS]
        parts.append(f"{n}. {comment.where}\n   > {code}\n   {comment.text.strip()}")
    return "\n\n".join(parts)
