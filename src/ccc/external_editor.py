"""Writing a message in an external editor (Ctrl+E in a text box): ccc
steps aside, the editor opens the text, and what you saved comes back
into the box — never sent by itself.

The editor is chosen in Settings among the ones installed here (found in
PATH; graphical ones only with a display). Auto = $VISUAL / $EDITOR,
else the first installed one. The text goes through a file in ccc's
folder (0600), deleted afterwards."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

SETTING_KEY = "external_editor"
AUTO = ""


@dataclass(frozen=True)
class Editor:
    id: str  # what the setting stores
    label: str
    argv: tuple[str, ...]  # the file is appended
    gui: bool = False


# Terminal editors first: ccc mostly runs in a terminal, often over SSH.
EDITORS: tuple[Editor, ...] = (
    Editor("nano", "nano", ("nano",)),
    Editor("micro", "micro", ("micro",)),
    Editor("vim", "vim", ("vim",)),
    Editor("nvim", "nvim", ("nvim",)),
    Editor("vi", "vi", ("vi",)),
    Editor("emacs", "emacs -nw", ("emacs", "-nw")),
    Editor("hx", "hx (Helix)", ("hx",)),
    Editor("kak", "kak (Kakoune)", ("kak",)),
    Editor("mcedit", "mcedit", ("mcedit",)),
    Editor("code", "code --wait (VS Code)", ("code", "--wait"), gui=True),
    Editor("codium", "codium --wait (VSCodium)", ("codium", "--wait"), gui=True),
    Editor("subl", "subl --wait (Sublime Text)", ("subl", "--wait"), gui=True),
    Editor("gedit", "gedit --wait", ("gedit", "--wait"), gui=True),
    Editor("kate", "kate --block", ("kate", "--block"), gui=True),
)
BY_ID = {e.id: e for e in EDITORS}


def has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def installed() -> list[Editor]:
    """The editors that can run here."""
    gui = has_display()
    return [e for e in EDITORS if (gui or not e.gui) and shutil.which(e.argv[0])]


def from_environment() -> tuple[str, ...] | None:
    """$VISUAL, else $EDITOR, when it names a program that exists."""
    for name in ("VISUAL", "EDITOR"):
        try:
            argv = tuple(shlex.split(os.environ.get(name, "")))
        except ValueError:
            continue
        if argv and shutil.which(argv[0]):
            return argv
    return None


def command(storage) -> tuple[str, ...] | None:
    """The editor to run: the one chosen in Settings while it's still
    installed, else $VISUAL / $EDITOR, else the first installed one."""
    chosen = BY_ID.get(storage.get_setting(SETTING_KEY) or AUTO)
    if chosen is not None and chosen in installed():
        return chosen.argv
    argv = from_environment()
    if argv is not None:
        return argv
    found = installed()
    return found[0].argv if found else None


def edit(argv: tuple[str, ...], text: str, folder: Path, run=subprocess.run) -> str | None:
    """Open text in the editor; the saved text, or None when nothing
    changed (closed without saving, or the editor failed)."""
    folder.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="ccc-message-", suffix=".md", dir=folder)  # 0600
    path = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        if run([*argv, str(path)]).returncode != 0:
            return None
        new = path.read_text(encoding="utf-8")
    finally:
        path.unlink(missing_ok=True)
    if not text.endswith("\n") and new.endswith("\n"):
        new = new[:-1]  # the newline editors add at the end of the file
    return None if new == text else new
