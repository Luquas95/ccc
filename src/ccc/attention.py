"""Which conversations need you right now — shown in the Claude Code pane's
title bar (tui.cli_pane), so you see them while you type into Claude Code,
and where the jump key (Alt+N) goes. The same states as the markers in the
Conversations list (tui.layout.queue_marker): a tool approval waiting, an
error, paused at a usage limit, a finished run you haven't seen yet."""
from __future__ import annotations

from dataclasses import dataclass

from ccc.i18n import N_, _
from ccc.models import QueueStatus

APPROVAL, ERROR, LIMIT, DONE = "approval", "error", "limit", "done"
# Most urgent first: the jump key goes to the first one.
ORDER = (APPROVAL, ERROR, LIMIT, DONE)
ICONS = {APPROVAL: "?", ERROR: "✖", LIMIT: "‖", DONE: "◆"}
LABELS = {
    APPROVAL: N_("waits for approval"),
    ERROR: N_("error"),
    LIMIT: N_("paused at a limit"),
    DONE: N_("done"),
}


@dataclass(frozen=True)
class Waiting:
    queue_id: int
    name: str
    kind: str

    def text(self) -> str:
        return f"{ICONS[self.kind]} {self.name} {_(LABELS[self.kind])}"


def waiting(storage, exclude: int | None = None) -> list[Waiting]:
    """Conversations (not archived, not `exclude` — the one you're looking
    at) that need you, most urgent first."""
    approvals = storage.queues_waiting_for_approval()
    unseen = storage.unseen_queue_ids()
    found = []
    for queue in storage.list_queues():
        if queue.archived or queue.id == exclude:
            continue
        if queue.id in approvals:
            kind = APPROVAL
        elif queue.status == QueueStatus.BLOCKED_ERROR:
            kind = ERROR
        elif queue.status in (QueueStatus.PAUSED_LIMIT, QueueStatus.WAITING_RETRY):
            kind = LIMIT
        elif queue.id in unseen and queue.status == QueueStatus.IDLE:
            kind = DONE
        else:
            continue
        found.append(Waiting(queue.id, queue.name, kind))
    return sorted(found, key=lambda w: ORDER.index(w.kind))


def summary(items: list[Waiting], width: int) -> str:
    """The items joined by " · ", cut to `width` characters with "+N more"
    for the ones that don't fit; "" when nothing waits."""
    if not items:
        return ""
    for shown in range(len(items), 0, -1):
        text = " · ".join(item.text() for item in items[:shown])
        if shown < len(items):
            text += " · " + _("+{n} more").format(n=len(items) - shown)
        if len(text) <= width:
            return text
    first = items[0].text()
    rest = (" · " + _("+{n} more").format(n=len(items) - 1)) if len(items) > 1 else ""
    room = max(1, width - len(rest))
    return (first[:room - 1] + "…" if len(first) > room else first) + rest
