"""Which columns the Dashboard shows — chosen in Settings, one choice for
a wide terminal and one for a narrow one (a phone: NARROW_COLUMNS wide
or less). The conversation's name (Project) is always there."""
from __future__ import annotations

from ccc.i18n import N_

# A window this narrow (or narrower) is "narrow": a phone over SSH / Termux.
NARROW_COLUMNS = 100

STATUS, PENDING, TOKENS, CONTEXT, GIT, PATH = "status", "pending", "tokens", "context", "git", "path"
# In table order, with the heading each has.
COLUMNS: tuple[tuple[str, str], ...] = (
    (STATUS, N_("Status")),
    (PENDING, N_("Pending")),
    (TOKENS, N_("Today's tokens")),
    (CONTEXT, N_("Context")),
    (GIT, N_("Git")),
    (PATH, N_("Path")),
)
IDS = tuple(column for column, _title in COLUMNS)
WIDE_KEY = "dashboard_columns"
NARROW_KEY = "dashboard_columns_narrow"
DEFAULT_WIDE = IDS
DEFAULT_NARROW = (STATUS, CONTEXT)


def is_narrow(width: int) -> bool:
    return width <= NARROW_COLUMNS


def _key(narrow: bool) -> str:
    return NARROW_KEY if narrow else WIDE_KEY


def shown(storage, narrow: bool) -> list[str]:
    """The chosen column ids in table order; the default until chosen
    (saved empty = none, so Project alone)."""
    raw = storage.get_setting(_key(narrow))
    if raw is None:
        chosen = DEFAULT_NARROW if narrow else DEFAULT_WIDE
    else:
        chosen = tuple(part for part in raw.split(",") if part)
    return [column for column in IDS if column in chosen]


def save(storage, narrow: bool, columns: list[str]) -> None:
    storage.set_setting(_key(narrow), ",".join(column for column in IDS if column in columns))
