"""Where ccc writes files for you: exported conversations (e) and
screenshots (Ctrl+T), each in its own subfolder of one export folder.

The folder is the "Export folder" setting; empty means the default —
ccc/ in your documents folder, whatever it's called in your language
(XDG user dirs: "Documents", "Dokumenty", …), or ~/ccc where there's none
(servers, Termux)."""
from __future__ import annotations

import os
import shlex
from pathlib import Path

FOLDER_KEY = "export_folder"
CONVERSATIONS = "conversations"
SCREENSHOTS = "screenshots"


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
    return (documents_dir(home, config_home) or home) / "ccc"


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
