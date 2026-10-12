import subprocess

import pytest

from cc_continue import managed_sessions as ms
from cc_continue.models import DeliveryMode, Queue


def _queue(**kw):
    base = dict(id=7, name="my conv", project_path="/tmp/p", session_id="sid-1",
                delivery_mode=DeliveryMode.REMOTE_CONTROL, launch_flags=["--model", "haiku"])
    base.update(kw)
    return Queue(**base)


def test_command_new_session_uses_session_id():
    assert ms.build_interactive_command(_queue(), has_transcript=False) == [
        "claude", "--session-id", "sid-1", "--remote-control", "my conv", "--model", "haiku",
    ]


def test_command_existing_session_resumes():
    assert ms.build_interactive_command(_queue(), has_transcript=True)[1:3] == ["--resume", "sid-1"]


def test_command_first_run_flags_pick_the_session():
    q = _queue(first_run_flags=["--resume", "orig", "--fork-session"])
    assert ms.build_interactive_command(q, has_transcript=False)[:4] == ["claude", "--resume", "orig", "--fork-session"]


def test_parse_remote_url_and_trust_prompt():
    pane = "  /remote-control is active · Continue here, on your phone, or at https://claude.ai/code/session_012kihHi2x9g\n"
    assert ms.parse_remote_url(pane) == "https://claude.ai/code/session_012kihHi2x9g"
    assert ms.parse_remote_url("nothing here") is None
    assert ms.needs_trust_confirmation("Do you trust the files in this folder?\n❯ 1. Yes, proceed")
    assert not ms.needs_trust_confirmation("❯ Řekni jen OK")


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    def fake_run(args, input_text=None):
        recorded.append((args, input_text))
        if "has-session" in args:
            return subprocess.CompletedProcess(args, 1, "", "")
        if "display-message" in args:
            return subprocess.CompletedProcess(args, 0, "4242\n", "")
        if "capture-pane" in args:
            return subprocess.CompletedProcess(args, 0, "pane text\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(ms, "_run", fake_run)
    return recorded


def test_tmux_calls_use_own_socket_and_target(calls):
    q = _queue()
    assert ms.is_running(q.id) is False
    ms.start(q, ["claude", "--session-id", "sid-1", "--remote-control", "my conv"])
    assert ms.pane_pid(q.id) == 4242
    assert ms.capture(q.id) == "pane text\n"
    ms.stop(q.id)
    for args, _ in calls:
        assert args[:3] == ["tmux", "-L", ms.TMUX_SOCKET]
    start_args = calls[1][0]
    assert "new-session" in start_args and "-c" in start_args and "/tmp/p" in start_args
    assert start_args[-1] == "claude --session-id sid-1 --remote-control 'my conv'"
    assert calls[-1][0][3:] == ["kill-session", "-t", "q7"]


def test_paste_and_submit_uses_bracketed_paste(calls):
    result = ms.paste_and_submit(7, "line one\nline two")
    assert result.delivered
    kinds = [args[3] for args, _ in calls]
    assert kinds == ["load-buffer", "paste-buffer", "send-keys"]
    assert calls[0][1] == "line one\nline two"
    assert "-p" in calls[1][0] and "-d" in calls[1][0]
    assert calls[2][0][-1] == "Enter"
