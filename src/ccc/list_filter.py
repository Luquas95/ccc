"""The filter over the list of Conversations / Archive (f): words matched
against a conversation's name and folder — case and diacritics don't
matter — and state markers at the start:

    !  Claude is working        ?  waiting for your approval
    x  stopped on an error      *  a new reply you haven't seen

A marker is a word of its own (`? api`, `!? api`, `x`); several markers
mean any of those states, several words must all match."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from ccc.models import Queue, QueueStatus

WORKING, APPROVAL, ERROR, UNSEEN = "!", "?", "x", "*"
MARKERS = frozenset((WORKING, APPROVAL, ERROR, UNSEEN))


def fold(text: str) -> str:
    """Lower case without diacritics: "Příliš" -> "prilis"."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@dataclass(frozen=True)
class ListFilter:
    states: frozenset[str] = frozenset()
    words: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return bool(self.states or self.words)

    def matches(self, queue: Queue, unseen: bool = False, needs_approval: bool = False) -> bool:
        if self.states and not self.states & _states(queue, unseen, needs_approval):
            return False
        haystack = fold(f"{queue.name} {queue.project_path}")
        return all(word in haystack for word in self.words)


def parse(text: str) -> ListFilter:
    tokens = text.split()
    states: set[str] = set()
    while tokens and set(tokens[0].lower()) <= MARKERS:
        states |= set(tokens.pop(0).lower())
    return ListFilter(frozenset(states), tuple(fold(t) for t in tokens))


def _states(queue: Queue, unseen: bool, needs_approval: bool) -> set[str]:
    states = set()
    if queue.status == QueueStatus.RUNNING:
        states.add(WORKING)
    if needs_approval:
        states.add(APPROVAL)
    if queue.status == QueueStatus.BLOCKED_ERROR:
        states.add(ERROR)
    if unseen:
        states.add(UNSEEN)
    return states
