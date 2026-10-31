"""What a device may do (#160). Every device has a role (models.ROLES): a
stolen phone or token should not be a way into the whole computer, so only
what a device needs is open to it. Weakest first:

read     only looks: every GET (lists, conversations, diffs, the events stream)
operate  also steers the conversations that exist: messages, approvals, queue,
         tasks, reviews, goals, workflows
admin    also what reaches beyond them: new conversations (any folder), keys
         typed into a terminal, prompts to live sessions, routines, reverting,
         settings, backup, updating ccc and building the app, other devices

The rules are in one table, checked before any handler runs; a path the table
doesn't know needs admin (closed by default)."""
from __future__ import annotations

import re

from ccc.models import ROLE_ADMIN, ROLE_OPERATE, ROLE_READ, ROLES

# (method or "*", path after /api/v1, role the request needs); the first match counts.
RULES: tuple[tuple[str, str, str], ...] = (
    ("*", r"/(app/build|update|update/check|backup)", ROLE_ADMIN),
    ("*", r"/settings(/.*)?", ROLE_ADMIN),
    ("POST", r"/conversations", ROLE_ADMIN),
    ("*", r"/conversations/\d+/terminal", ROLE_ADMIN),
    ("POST", r"/live-sessions/[^/]+/prompt", ROLE_ADMIN),
    ("*", r"/routines(/.*)?", ROLE_ADMIN),
    ("POST", r"/runs/\d+/revert", ROLE_ADMIN),
    ("*", r"/devices/\d+", ROLE_ADMIN),  # a device's own rename and sign-out are let through in required_role()
    ("GET", r"/.*", ROLE_READ),
    ("*", r"/(conversations/\d+/(messages|retry|seen|archive|group|tasks|reviews|reviews/stop|goals|goals/stop|"
          r"workflows|workflows/answer|workflows/stop|asks)|tasks/\d+(/move)?|reviews/\d+/apply|asks/\d+/cancel|"
          r"runs/\d+/comments|groups(/rename|/delete)?|permissions/\d+|"
          r"prompt-presets|launch-presets(/delete)?|analytics/archive)", ROLE_OPERATE),
)
_COMPILED = tuple((method, re.compile(pattern), role) for method, pattern, role in RULES)
_OWN_DEVICE = re.compile(r"/devices/(\d+)")


def required_role(method: str, rest: str, device_id: int | None = None) -> str:
    """The weakest role that may make this request (`rest` is the path after /api/v1).
    A device may rename and sign out itself whatever its role."""
    rest = rest.rstrip("/") or "/"
    own = _OWN_DEVICE.fullmatch(rest)
    if own and device_id is not None and int(own.group(1)) == device_id and method in ("POST", "DELETE"):
        return ROLE_READ
    for rule_method, pattern, role in _COMPILED:
        if rule_method in ("*", method) and pattern.fullmatch(rest):
            return role
    return ROLE_ADMIN


def allows(role: str, needed: str) -> bool:
    """Does a device with `role` reach what needs `needed`? An unknown role counts as the weakest."""
    return ROLES.index(needed) <= (ROLES.index(role) if role in ROLES else 0)
