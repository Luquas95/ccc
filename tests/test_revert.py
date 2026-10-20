import argparse
import subprocess
from datetime import datetime

import pytest

from ccc import gitops, revert, revert_cli
from ccc.models import ItemStatus, PromptRun, RunStatus
from ccc.storage import Storage


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    (path / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "init")
    return path


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "h.db")


def _run_with_commit(storage, queue, repo, text="return a - b"):
    (repo / "calc.py").write_text(f"def add(a, b):\n    {text}\n")
    _git(repo, "commit", "-qam", f"ccc: {text}")
    return storage.find_run(storage.insert_prompt_run(PromptRun(
        id=0, queue_id=queue.id, queue_item_id=None, prompt_text=f"change to {text}", started_at=datetime.now(),
        finished_at=datetime.now(), status=RunStatus.SUCCESS, git_commit=_git(repo, "rev-parse", "HEAD"),
    )))


def test_revert_makes_a_new_commit_and_marks_the_run(storage, repo):
    queue = storage.create_queue("calc", str(repo), "s1")
    run = _run_with_commit(storage, queue, repo)
    commit = revert.revert(storage, run)
    assert (repo / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    assert _git(repo, "rev-parse", "HEAD") == commit
    message = _git(repo, "log", "-1", "--format=%B")
    assert message.startswith(f"ccc: revert {run.git_commit[:7]}") and f"ccc-reverts: {run.git_commit}" in message
    assert storage.find_run(run.id).reverted_by == commit
    with pytest.raises(revert.RevertError, match="already reverted"):
        revert.revert(storage, storage.find_run(run.id))


def test_a_conflicting_revert_changes_nothing(storage, repo):
    queue = storage.create_queue("calc", str(repo), "s1")
    run = _run_with_commit(storage, queue, repo, "return a - b")
    _run_with_commit(storage, queue, repo, "return a * b")  # later change on the same line
    head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(revert.RevertError, match="conflicts"):
        revert.revert(storage, run)
    assert _git(repo, "rev-parse", "HEAD") == head and _git(repo, "status", "--porcelain") == ""
    assert storage.find_run(run.id).reverted_by is None


def test_uncommitted_changes_block_it(storage, repo):
    queue = storage.create_queue("calc", str(repo), "s1")
    run = _run_with_commit(storage, queue, repo)
    (repo / "notes.txt").write_text("mine")
    with pytest.raises(revert.RevertError, match="uncommitted"):
        revert.revert(storage, run)


def test_only_while_idle_and_where_claude_may_run_commands(storage, repo):
    busy = storage.create_queue("calc", str(repo), "s1")
    run = _run_with_commit(storage, busy, repo)
    storage.add_queue_item(busy.id, "next")
    with pytest.raises(revert.RevertError, match="working"):
        revert.check(storage, run)
    restricted = storage.create_queue("ro", str(repo), "s2", launch_flags=["--permission-mode", "acceptEdits"])
    run2 = storage.find_run(storage.insert_prompt_run(PromptRun(
        id=0, queue_id=restricted.id, queue_item_id=None, prompt_text="x", started_at=datetime.now(),
        finished_at=datetime.now(), status=RunStatus.SUCCESS, git_commit=run.git_commit)))
    with pytest.raises(revert.RevertError, match="Skip all permission checks"):
        revert.check(storage, run2)


def test_a_run_without_a_commit_has_nothing_to_revert(storage, repo):
    queue = storage.create_queue("calc", str(repo), "s1")
    run = storage.find_run(storage.insert_prompt_run(PromptRun(
        id=0, queue_id=queue.id, queue_item_id=None, prompt_text="x", started_at=datetime.now(),
        finished_at=datetime.now(), status=RunStatus.SUCCESS)))
    with pytest.raises(revert.RevertError, match="no commit"):
        revert.check(storage, run)


def test_revert_commit_refuses_odd_input(repo):
    assert gitops.revert_commit(str(repo), "--hard", "c").commit is None
    assert "history" in gitops.revert_commit(str(repo), "0" * 40, "c").note


def test_tell_claude_queues_a_note(storage, repo):
    queue = storage.create_queue("calc", str(repo), "s1")
    run = _run_with_commit(storage, queue, repo)
    item = revert.tell_claude(storage, run, "abcdef0123456")
    assert "abcdef0" in item.prompt_text and "change to return a - b" in item.prompt_text
    assert item.status == ItemStatus.PENDING


def _cli(*argv):
    parser = argparse.ArgumentParser()
    revert_cli.add_parser(parser.add_subparsers(dest="command"))
    return parser.parse_args(argv)


def test_cli_runs_and_revert(storage, repo, capsys):
    queue = storage.create_queue("calc", str(repo), "s1")
    run = _run_with_commit(storage, queue, repo)
    assert revert_cli.run_runs(storage, _cli("runs", "calc")) == 0
    assert run.git_commit[:7] in capsys.readouterr().out
    assert revert_cli.run_revert(storage, _cli("revert", str(run.id), "--tell")) == 0
    assert storage.find_run(run.id).reverted_by and storage.list_pending_items(queue.id)
    assert revert_cli.run_revert(storage, _cli("revert", "999")) == 1
