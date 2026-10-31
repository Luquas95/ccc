import subprocess
from pathlib import Path

import pytest

from ccc import daemon, updates
from ccc.models import QueueStatus
from ccc.storage import Storage


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True)


@pytest.fixture
def repos(tmp_path):
    """origin (bare), the ccc checkout (a clone on main) and a second clone that pushes."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    ccc = tmp_path / "ccc"
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(origin), str(ccc)], check=True, capture_output=True)
    (ccc / "a.txt").write_text("one\n")
    git(ccc, "add", "."); git(ccc, "commit", "-qm", "first"); git(ccc, "push", "-q", "origin", "main")
    subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True, capture_output=True)
    return ccc, other


def push(other, name="b.txt", subject="second", folder=""):
    path = other / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(subject)
    git(other, "add", "."); git(other, "commit", "-qm", subject); git(other, "push", "-q", "origin", "main")


@pytest.fixture
def storage(tmp_path):
    return Storage(str(tmp_path / "h.db"))


def test_up_to_date_then_new_commits(repos, storage):
    ccc, other = repos
    assert not updates.check(storage, ccc).available
    push(other, subject="Add rate limiting")
    push(other, "c.txt", "Fix the login", folder="android/app/src/main")
    state = updates.check(storage, ccc)
    assert state.available and state.behind == 2 and state.error is None
    assert [c.split(" ", 1)[1] for c in state.commits] == ["Fix the login", "Add rate limiting"]
    assert state.android  # one of them changes the Android app
    assert updates.load(storage) == state  # kept for the TUI, the API and the phone


def test_commits_outside_the_app_dont_make_it_stale(repos, storage):
    ccc, other = repos
    push(other, folder="src")
    assert not updates.check(storage, ccc).android


def test_a_fetch_that_fails_is_an_error_not_a_crash(repos, storage):
    ccc, _other = repos
    git(ccc, "remote", "set-url", "origin", str(ccc.parent / "nowhere.git"))
    state = updates.check(storage, ccc)
    assert state.error and not state.available
    assert updates.load(storage).error == state.error


def test_apply_pulls_and_starts_the_install(repos, storage):
    ccc, other = repos
    push(other, subject="Add rate limiting")
    spawned = []
    ok, message = updates.apply(storage, ccc, spawn=lambda command, log: spawned.append((command, log)),
                                units=lambda: ["ccc.service", "ccc-tui.service"])
    assert ok and "restarting" in message
    assert (ccc / "b.txt").exists()
    command, log = spawned[0]
    assert command.endswith("--no-start && systemctl --user restart ccc.service ccc-tui.service")
    assert "--no-tui" not in command and "--api" not in command
    assert log.name == "update.log"
    assert not updates.load(storage).available  # nothing new now


@pytest.mark.parametrize("units, expected", [
    (["ccc.service"], "--no-start --no-tui"),
    (["ccc.service", "ccc-tui.service", "ccc-api.service"], "--no-start --api"),
    ([], "--no-systemd"),
])
def test_install_flags_follow_how_it_was_installed(units, expected):
    command = updates.install_command(units, Path("/opt/ccc"))
    assert f"/opt/ccc/bin/install.sh {expected}" in command
    assert ("systemctl" in command) == bool(units)


@pytest.mark.parametrize("prepare, word", [
    (lambda ccc, other, st: git(ccc, "checkout", "-qb", "feature"), "feature"),
    (lambda ccc, other, st: (ccc / "a.txt").write_text("changed\n"), "uncommitted"),
    (lambda ccc, other, st: (((ccc / "x.txt").write_text("x"), git(ccc, "add", "."), git(ccc, "commit", "-qm", "local"))),
     "aren't on"),
    (lambda ccc, other, st: st.update_queue_status(st.create_queue("shop", "/tmp", "s1").id, QueueStatus.RUNNING),
     "shop"),
])
def test_apply_refuses_when_it_isnt_safe_and_changes_nothing(repos, storage, prepare, word):
    ccc, other = repos
    push(other)
    prepare(ccc, other, storage)
    spawned = []
    ok, message = updates.apply(storage, ccc, spawn=lambda *a: spawned.append(a), units=lambda: [])
    assert not ok and word in message
    assert spawned == [] and not (ccc / "b.txt").exists()  # nothing was pulled


def test_apply_when_up_to_date(repos, storage):
    ccc, _other = repos
    ok, message = updates.apply(storage, ccc, spawn=lambda *a: pytest.fail("nothing to install"), units=lambda: [])
    assert not ok and "up to date" in message


def test_android_build_counts_the_commits_that_changed_the_app(repos):
    ccc, other = repos
    assert updates.android_build(ccc) == 0
    push(other, folder="android/app/src/main")
    git(ccc, "pull", "-q")
    assert updates.android_build(ccc) == 1


class _Notifier:
    def __init__(self):
        self.sent = []

    def send_now(self, text, category=None):
        self.sent.append(text)
        return True


def test_the_daemon_tells_once_per_new_head(repos, storage):
    ccc, other = repos
    notifier = _Notifier()
    assert daemon.update_tick(storage, notifier, ccc) is None  # nothing new
    push(other, subject="Add rate limiting")
    text = daemon.update_tick(storage, notifier, ccc)
    assert "1 new commit" in text and "Add rate limiting" in text
    assert daemon.update_tick(storage, notifier, ccc) is None  # the same head: not again
    push(other, "c.txt", "Another")
    assert daemon.update_tick(storage, notifier, ccc) is not None
    assert len(notifier.sent) == 2


def test_the_check_can_be_turned_off(repos, storage):
    ccc, other = repos
    push(other)
    storage.set_setting(updates.CHECK_KEY, "off")
    assert daemon.update_tick(storage, _Notifier(), ccc) is None
    assert not updates.load(storage).available
