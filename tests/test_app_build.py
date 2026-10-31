import subprocess
import time
from pathlib import Path

import pytest

from ccc import app_build, updates
from ccc.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(str(tmp_path / "ccc.db"))


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(app_build, "_building", False)
    monkeypatch.setattr(app_build, "_error", None)
    monkeypatch.setattr(updates, "android_build", lambda repo=updates.PROJECT_DIR: 7)


def _wait():
    for _ in range(100):
        if not app_build._building:
            return
        time.sleep(0.02)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "android").mkdir(parents=True)
    return repo


def test_a_build_keeps_the_apk_by_build_number(storage, tmp_path):
    repo = _repo(tmp_path)

    def gradle(cmd, cwd, **kwargs):
        apk = Path(cwd) / app_build.BUILT_APK
        apk.parent.mkdir(parents=True)
        apk.write_bytes(b"apk")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    assert app_build.status(storage)["ready"] is False
    app_build.start(storage, repo, gradle)
    _wait()
    state = app_build.status(storage)
    assert state["ready"] is True and state["build"] == 7 and state["size"] == 3
    assert app_build.apk_path(storage).read_bytes() == b"apk"
    # Built: nothing runs again.
    assert app_build.start(storage, repo, lambda *a, **k: pytest.fail("built twice"))["ready"] is True


def test_a_failed_build_says_why(storage, tmp_path):
    repo = _repo(tmp_path)
    app_build.start(storage, repo, lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, "", "boom\nSDK missing\n"))
    _wait()
    state = app_build.status(storage)
    assert state["ready"] is False and state["building"] is False
    assert "SDK missing" in state["error"]
