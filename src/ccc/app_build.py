"""The Android app, built by ccc itself, so the phone can update over its own pairing.

ccc's checkout has the app's sources (android/). `build()` runs Gradle's
assembleDebug in the background and keeps the APK next to ccc's database as
ccc-<build>.apk, <build> being updates.android_build() — the version code the
app gets. The APK is signed with this computer's debug key (~/.android),
so a later build installs over an earlier one. The API tells the phone the
state (`status`) and sends the file (`apk_path`)."""
from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

from ccc import updates
from ccc.i18n import _

logger = logging.getLogger(__name__)

BUILD_TIMEOUT = 20 * 60
BUILT_APK = Path("app/build/outputs/apk/debug/app-debug.apk")

_lock = threading.Lock()
_building = False
_error: str | None = None


def _folder(storage) -> Path:
    return Path(storage.db_path).parent


def apk_path(storage, build: int | None = None) -> Path:
    return _folder(storage) / f"ccc-{build if build is not None else updates.android_build()}.apk"


def status(storage) -> dict:
    """{"build", "ready", "building", "error", "size"} for the checkout's current app build."""
    build = updates.android_build()
    apk = apk_path(storage, build)
    with _lock:
        building, error = _building, _error
    ready = apk.exists()
    return {"build": build, "ready": ready, "building": building, "error": None if ready else error,
            "size": apk.stat().st_size if ready else 0}


def start(storage, repo: Path = updates.PROJECT_DIR, run=subprocess.run) -> dict:
    """Build the app in the background unless it is built or building; returns `status`."""
    global _building, _error
    build = updates.android_build(repo)
    with _lock:
        busy = _building or apk_path(storage, build).exists()
        if not busy:
            _building, _error = True, None
    if busy:
        return status(storage)
    threading.Thread(target=_build, args=(storage, repo, build, run), daemon=True).start()
    return status(storage)


def _build(storage, repo: Path, build: int, run) -> None:
    global _building, _error
    error = None
    try:
        result = run(["./gradlew", "--console=plain", "-q", "assembleDebug"], cwd=repo / "android",
                     capture_output=True, text=True, timeout=BUILD_TIMEOUT)
        built = repo / "android" / BUILT_APK
        if result.returncode != 0 or not built.exists():
            lines = [line for line in (result.stderr or result.stdout).splitlines() if line.strip()]
            logger.error("App build failed:\n%s", "\n".join(lines[-20:]))
            error = _("The app could not be built: {why}").format(why=(lines[-1] if lines else "gradle")[:200])
        else:
            target = apk_path(storage, build)
            partial = target.with_suffix(".part")
            partial.write_bytes(built.read_bytes())
            partial.replace(target)
            for old in _folder(storage).glob("ccc-*.apk"):
                if old != target:
                    old.unlink(missing_ok=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.exception("App build failed")
        error = _("The app could not be built: {why}").format(why=type(exc).__name__)
    with _lock:
        _building, _error = False, error
