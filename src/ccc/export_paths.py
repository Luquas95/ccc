"""Where ccc writes files for you: exported conversations (e) and
screenshots (Alt+S), each in its own subfolder of one export folder.

The folder is the "Export folder" setting; empty means the default —
ccc/ in your documents folder, whatever it's called in your language
(XDG user dirs: "Documents", "Dokumenty", …), or ~/ccc-exports where
there's none (servers, Termux — not ~/ccc, where `git clone` puts this repo).

A saved export can also be sent to Telegram and/or Discord (the "After
export" setting), so it reaches you when ccc runs on another machine."""
from __future__ import annotations

import os
import shlex
from pathlib import Path

from ccc.i18n import N_

FOLDER_KEY = "export_folder"
CONVERSATIONS = "conversations"
SCREENSHOTS = "screenshots"
FALLBACK_NAME = "ccc-exports"

SEND_KEY = "export_send"
TELEGRAM = "telegram"
DISCORD = "discord"
# (setting value, label) — the file is always saved to the folder first.
SEND_CHOICES = [
    ("", N_("Only save to the folder")),
    (TELEGRAM, N_("Also send to Telegram")),
    (DISCORD, N_("Also send to Discord")),
    ("both", N_("Also send to Telegram and Discord")),
]


def documents_dir(home: Path | None = None, config_home: Path | None = None) -> Path | None:
    """The XDG documents folder from user-dirs.dirs, or None when it isn't
    set, doesn't exist or is just the home folder (XDG's "disabled")."""
    home = home or Path.home()
    config_home = config_home or Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    try:
        lines = (config_home / "user-dirs.dirs").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        key, sep, value = line.strip().partition("=")
        if key != "XDG_DOCUMENTS_DIR" or not sep:
            continue
        try:
            value = "".join(shlex.split(value))
        except ValueError:
            return None
        if value.startswith("$HOME"):
            path = home / value.removeprefix("$HOME").lstrip("/")
        elif value.startswith("/"):
            path = Path(value)
        else:
            return None
        return path if path != home and path.is_dir() else None
    return None


def default_export_folder(home: Path | None = None, config_home: Path | None = None) -> Path:
    home = home or Path.home()
    documents = documents_dir(home, config_home)
    return documents / "ccc" if documents else home / FALLBACK_NAME


def export_folder(storage) -> Path:
    folder = (storage.get_setting(FOLDER_KEY) or "").strip()
    return Path(folder).expanduser() if folder else default_export_folder()


def home_short(path: Path) -> str:
    """~/… for paths under the home folder, for hints."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def export_dir(storage, kind: str) -> Path:
    """The subfolder for one kind of export (CONVERSATIONS, SCREENSHOTS),
    created on first use."""
    path = export_folder(storage) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def send_targets(storage) -> list[str]:
    """Channels a saved export also goes to: [], [TELEGRAM], [DISCORD] or both."""
    value = storage.get_setting(SEND_KEY) or ""
    if value == "both":
        return [TELEGRAM, DISCORD]
    return [value] if value in (TELEGRAM, DISCORD) else []
