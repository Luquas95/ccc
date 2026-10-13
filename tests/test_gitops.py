import subprocess

import pytest

from ccc import gitops


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    (r / "a.txt").write_text("one\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    return r


def test_not_a_repo(tmp_path):
    assert gitops.snapshot(str(tmp_path)) is None


def test_clean_snapshot_then_commit(repo):
    before = gitops.snapshot(str(repo))
    assert before.clean and before.head
    (repo / "a.txt").write_text("two\n")
    (repo / "b.txt").write_text("new\n")
    outcome = gitops.commit_task(str(repo), before, "Fix things\nmore detail", "my conv")
    assert outcome.commit and outcome.commit != before.head
    log = _git(repo, "log", "-1", "--format=%s%n%b")
    assert log.startswith("ccc: Fix things") and "ccc-conversation: my conv" in log
    assert _git(repo, "status", "--porcelain") == ""
    shown = gitops.show(str(repo), outcome.commit)
    assert "b.txt" in shown and "+two" in shown


def test_no_changes_no_commit(repo):
    before = gitops.snapshot(str(repo))
    outcome = gitops.commit_task(str(repo), before, "noop", "c")
    assert outcome.commit is None and "no changes" in outcome.note


def test_dirty_before_task_is_not_committed(repo):
    (repo / "a.txt").write_text("my own wip\n")
    before = gitops.snapshot(str(repo))
    assert before.clean is False
    (repo / "c.txt").write_text("claude\n")
    outcome = gitops.commit_task(str(repo), before, "task", "c")
    assert outcome.commit is None and "uncommitted changes before" in outcome.note
    assert "a.txt" in _git(repo, "status", "--porcelain")  # untouched


def test_detached_head_is_not_committed(repo):
    head = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "checkout", "-q", head)
    before = gitops.snapshot(str(repo))
    (repo / "d.txt").write_text("x\n")
    outcome = gitops.commit_task(str(repo), before, "task", "c")
    assert outcome.commit is None and "detached" in outcome.note


def test_repo_hooks_and_fsmonitor_never_run(repo, tmp_path):
    marker = tmp_path / "pwned"
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    fsmon = tmp_path / "fsmon.sh"
    fsmon.write_text(f"#!/bin/sh\ntouch {marker}\n")
    fsmon.chmod(0o755)
    _git(repo, "config", "core.fsmonitor", str(fsmon))
    before = gitops.snapshot(str(repo))
    (repo / "a.txt").write_text("changed\n")
    outcome = gitops.commit_task(str(repo), before, "task", "c")
    gitops.show(str(repo), outcome.commit)
    assert outcome.commit
    assert not marker.exists()


def test_external_diff_driver_is_not_used_by_show(repo, tmp_path):
    marker = tmp_path / "pwned"
    tool = tmp_path / "extdiff.sh"
    tool.write_text(f"#!/bin/sh\ntouch {marker}\n")
    tool.chmod(0o755)
    _git(repo, "config", "diff.external", str(tool))
    before = gitops.snapshot(str(repo))
    (repo / "a.txt").write_text("changed\n")
    outcome = gitops.commit_task(str(repo), before, "task", "c")
    assert "+changed" in gitops.show(str(repo), outcome.commit)
    assert not marker.exists()


def test_claude_can_run_commands():
    from ccc.models import Queue

    def q(flags):
        return Queue(id=1, name="n", project_path="/p", session_id="s", launch_flags=flags)

    assert gitops.claude_can_run_commands(q(None))  # legacy queues ran with skip-permissions
    assert gitops.claude_can_run_commands(q(["--dangerously-skip-permissions", "--model", "opus"]))
    assert gitops.claude_can_run_commands(q(["--permission-mode", "bypassPermissions"]))
    assert not gitops.claude_can_run_commands(q(["--permission-mode", "acceptEdits"]))
    assert not gitops.claude_can_run_commands(q(["--permission-mode", "plan"]))
    assert not gitops.claude_can_run_commands(q([]))
