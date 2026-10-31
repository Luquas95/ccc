"""ccc updating itself: is there something new on origin/main, and apply it.

ccc is a git checkout (bin/install.sh: editable install, systemd user
units), so an update is `git pull --ff-only` and the install script again,
then the services restart. Looking is harmless (`git fetch`); applying
runs only on a yes — in the TUI's Update window or from the phone — and
only as a fast-forward of main in a clean checkout, while no task runs: the
code that arrives is whatever was pushed to origin/main.

The result of the last look is kept in the `update_state` setting (JSON),
so every reader — the TUI, the API, the daemon's notice — sees the same.
The daemon looks every CHECK_SECONDS (check_enabled(): Settings)."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from ccc.i18n import _
from ccc.models import QueueStatus

STATE_KEY = "update_state"
CHECK_KEY = "update_check"  # "" = on, "off"
BRANCH = "main"
REMOTE = "origin"
CHECK_SECONDS = 6 * 3600.0
SHOWN_COMMITS = 10
FETCH_TIMEOUT = 40
# The Android app's sources: what makes a new app build necessary.
ANDROID_SOURCES = "android/app/src/main"
UNITS = ("ccc.service", "ccc-tui.service", "ccc-api.service")
PROJECT_DIR = Path(__file__).resolve().parents[2]


@dataclass
class UpdateState:
    checked_at: str | None = None
    behind: int = 0
    commits: list[str] = field(default_factory=list)  # "abc1234 subject", newest first
    remote_head: str | None = None
    android: bool = False  # the new commits change the Android app
    error: str | None = None
    # The remote head already told to Telegram / Discord, so it's said once.
    notified_head: str | None = None

    @property
    def available(self) -> bool:
        return self.behind > 0


def load(storage) -> UpdateState:
    try:
        return UpdateState(**json.loads(storage.get_setting(STATE_KEY) or "{}"))
    except (ValueError, TypeError):
        return UpdateState()


def save(storage, state: UpdateState) -> None:
    storage.set_setting(STATE_KEY, json.dumps(asdict(state)))


def check_enabled(storage) -> bool:
    return storage.get_setting(CHECK_KEY) != "off"


def _git(repo: Path, *args: str, timeout: float = 15) -> subprocess.CompletedProcess:
    # Never ask for a password: a fetch that needs one fails.
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true", "LC_ALL": "C"}
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout, env=env)


def android_build(repo: Path = PROJECT_DIR) -> int:
    """How many commits changed the Android app's sources: its build number
    (android/app/build.gradle.kts counts the same way), so a pull that
    changes the app makes the phone's build older than ccc's."""
    try:
        out = _git(repo, "rev-list", "--count", "HEAD", "--", ANDROID_SOURCES).stdout.strip()
        return int(out)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return 0


def check(storage, repo: Path = PROJECT_DIR) -> UpdateState:
    """Fetch origin/main and compare with this checkout; the outcome is
    saved (an error as well — "can't look" is something to show)."""
    previous = load(storage)
    state = UpdateState(checked_at=datetime.now().isoformat(timespec="seconds"), notified_head=previous.notified_head)
    try:
        fetched = _git(repo, "fetch", "--quiet", REMOTE, BRANCH, timeout=FETCH_TIMEOUT)
        if fetched.returncode != 0:
            # Only the first line: git's message may name the remote's URL.
            state.error = (fetched.stderr.strip().splitlines() or ["git fetch failed"])[0][:200]
        else:
            ref = f"{REMOTE}/{BRANCH}"
            state.behind = int(_git(repo, "rev-list", "--count", f"HEAD..{ref}").stdout.strip() or 0)
            state.remote_head = _git(repo, "rev-parse", "--short", ref).stdout.strip() or None
            if state.behind:
                log = _git(repo, "log", f"-n{SHOWN_COMMITS}", "--format=%h %s", f"HEAD..{ref}").stdout
                state.commits = [line for line in log.splitlines() if line]
                changed = _git(repo, "diff", "--name-only", f"HEAD...{ref}", "--", ANDROID_SOURCES).stdout
                state.android = bool(changed.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        state.error = type(exc).__name__
    save(storage, state)
    return state


def refusal(storage, repo: Path = PROJECT_DIR) -> str | None:
    """Why an update can't be applied now, in words for the user; None when it can."""
    try:
        branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if branch != BRANCH:
            return _("The checkout is on branch “{branch}”, not {main}.").format(branch=branch, main=BRANCH)
        if _git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
            return _("The checkout has uncommitted changes.")
        ahead = _git(repo, "rev-list", "--count", f"{REMOTE}/{BRANCH}..HEAD").stdout.strip()
        if ahead not in ("", "0"):
            return _("The checkout has commits that aren't on {remote}/{main}.").format(remote=REMOTE, main=BRANCH)
    except (OSError, subprocess.TimeoutExpired):
        return _("git can't be run in the ccc checkout.")
    running = [q.name for q in storage.list_queues() if q.status == QueueStatus.RUNNING and not q.archived]
    if running:
        return _("A task is running ({names}) — the restart would stop it.").format(names=", ".join(running[:3]))
    return None


def installed_units() -> list[str]:
    """The ccc systemd user units this checkout was installed with."""
    folder = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user"
    return [unit for unit in UNITS if (folder / unit).exists()]


def install_command(units: list[str], repo: Path = PROJECT_DIR) -> str:
    """The shell line after the pull: the install script (the same options
    this checkout was installed with, not starting anything), then the
    units restarted — `enable --now` leaves running ones on the old code."""
    flags = ["--no-start"]
    if "ccc-tui.service" not in units:
        flags.append("--no-tui")
    if "ccc-api.service" in units:
        flags.append("--api")
    if not units:
        flags = ["--no-systemd"]
    line = f"{shlex.quote(str(repo / 'bin' / 'install.sh'))} {' '.join(flags)}"
    if units:
        line += " && systemctl --user restart " + " ".join(units)
    return line


def spawn_install(command: str, log: Path) -> None:
    """Run `command` outside this process: the restart stops the TUI /
    daemon / API that asked for it. In its own transient unit when systemd
    has one (its cgroup isn't the restarted unit's), else detached."""
    script = f"{command} >> {shlex.quote(str(log))} 2>&1"
    if shutil.which("systemd-run") and subprocess.run(
            ["systemctl", "--user", "show-environment"], capture_output=True).returncode == 0:
        subprocess.Popen(["systemd-run", "--user", "--collect", "--quiet", "--unit", "ccc-update", "bash", "-c", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["bash", "-c", script], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def apply(storage, repo: Path = PROJECT_DIR, spawn=spawn_install, units=installed_units) -> tuple[bool, str]:
    """Pull and restart. (True, message) once it's on its way; (False, why)
    when not — nothing is changed then."""
    state = check(storage, repo)
    if state.error:
        return False, _("Can't look for the update: {error}").format(error=state.error)
    if not state.available:
        return False, _("ccc is up to date.")
    reason = refusal(storage, repo)
    if reason:
        return False, reason
    pulled = _git(repo, "pull", "--ff-only", "--quiet", REMOTE, BRANCH, timeout=FETCH_TIMEOUT * 3)
    if pulled.returncode != 0:
        return False, (pulled.stderr.strip().splitlines() or ["git pull failed"])[0][:200]
    log = _log_path(storage)
    spawn(install_command(units(), repo), log)
    save(storage, UpdateState(checked_at=state.checked_at, notified_head=state.remote_head))
    return True, _("Updated to {head} — ccc is restarting.").format(head=state.remote_head)


def _log_path(storage) -> Path:
    return Path(storage.db_path).parent / "update.log"


def notice(state: UpdateState) -> str:
    """The message for Telegram / Discord."""
    lines = [_("⬆️ ccc update available: {n} new commit(s) on {branch}.").format(n=state.behind, branch=BRANCH)]
    lines += [f"• {commit}" for commit in state.commits[:5]]
    if state.android:
        lines.append(_("The Android app changed too — the phone gets it with the next release."))
    lines.append(_("Update it in ccc (Update window) or from the phone."))
    return "\n".join(lines)
