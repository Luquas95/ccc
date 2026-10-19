"""ccc speaks English or Czech.

Source strings are English and wrapped in _() (gettext style); the Czech
catalogue (cs.py) maps them to translations. A string without a
translation falls back to English, and tests/test_i18n.py checks that
every _("…") in the code has one.

The language is the `language` setting ("" = auto, "en", "cs"); auto
follows the system locale (LC_ALL / LC_MESSAGES / LANG). CCC_LANG in the
environment overrides both (tests run in English through it). The TUI
picks the language once at start — its keys and labels are built at
import time — so changing it restarts the TUI; the daemon reloads it
with every heartbeat (load()).
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

LANGUAGE_KEY = "language"
# (code, name in that language) — the choices in Settings.
LANGUAGES: list[tuple[str, str]] = [("en", "English"), ("cs", "Čeština")]
_CODES = {code for code, _name in LANGUAGES}

_current: str | None = None


def system_language() -> str:
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value:
            return "cs" if value.lower().startswith("cs") else "en"
    return "en"


def resolve(setting: str | None) -> str:
    """The language a `language` setting means ("" / None / "auto" = system)."""
    forced = os.environ.get("CCC_LANG", "")
    if forced in _CODES:
        return forced
    if setting in _CODES:
        return setting
    return system_language()


def _setting_from_default_db() -> str | None:
    # Read-only and quiet: a missing or locked database just means "auto".
    path = Path.home() / ".local" / "share" / "ccc" / "history.db"
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)
        try:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (LANGUAGE_KEY,)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def language() -> str:
    global _current
    if _current is None:
        forced = os.environ.get("CCC_LANG", "")
        _current = forced if forced in _CODES else resolve(_setting_from_default_db())
    return _current


def set_language(code: str) -> None:
    global _current
    _current = code if code in _CODES else "en"


def load(storage) -> str:
    """Take the language from this database's setting."""
    set_language(resolve(storage.get_setting(LANGUAGE_KEY)))
    return language()


def _(text: str) -> str:
    if language() == "en":
        return text
    from ccc.i18n.cs import CS

    return CS.get(text, text)


def N_(text: str) -> str:
    """Marks a string for translation where it's defined; _() translates
    it where it's shown (tables built once, the help generator's two
    languages)."""
    return text


_MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December"],
    "cs": ["leden", "únor", "březen", "duben", "květen", "červen", "červenec", "srpen", "září",
           "říjen", "listopad", "prosinec"],
}
_WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "cs": ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"],
}
_WEEKDAYS_SHORT = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "cs": ["po", "út", "st", "čt", "pá", "so", "ne"],
}


def month_title(year: int, month: int) -> str:
    """"October 2026" / "říjen 2026" — not strftime, which follows the
    process locale rather than ccc's language."""
    return f"{_MONTHS[language()][month - 1]} {year}"


def weekday_name(day) -> str:
    return _WEEKDAYS[language()][day.weekday()]


def weekday_short(day) -> str:
    return _WEEKDAYS_SHORT[language()][day.weekday()]
