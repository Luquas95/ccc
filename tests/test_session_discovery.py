import json
from unittest.mock import MagicMock, patch

from cc_continue.session_discovery import (
    DiscoveredSession,
    discover_sessions,
    find_tmux_pane_for_pid,
    session_ready_for_input,
)

REAL_SAMPLE_OUTPUT = json.dumps(
    [
        {
            "pid": 1280934,
            "id": "d61c8ea6",
            "cwd": "/home/lukas",
            "kind": "background",
            "startedAt": 1788377182066,
            "sessionId": "e1a59594-2c12-4488-9555-98331a713a24",
            "name": "DEV gallery projekt načtení",
            "status": "idle",
            "state": "blocked",
        },
        {
            "pid": 1611743,
            "cwd": "/home/lukas/DEV",
            "kind": "interactive",
            "startedAt": 1788405769995,
            "sessionId": "a65e24bb-eda1-4294-8ad0-b39f3cf8891d",
            "name": "dev-75",
            "status": "busy",
        },
        {"pid": 123, "cwd": "/tmp", "kind": "interactive", "name": "no-session-id"},
    ]
)


def test_discover_sessions_parses_real_shaped_output():
    fake_result = MagicMock(returncode=0, stdout=REAL_SAMPLE_OUTPUT)
    with patch("subprocess.run", return_value=fake_result):
        sessions = discover_sessions()

    assert len(sessions) == 2  # the malformed third entry (no sessionId) is skipped
    assert sessions[0].session_id == "e1a59594-2c12-4488-9555-98331a713a24"
    assert sessions[0].name == "DEV gallery projekt načtení"
    assert sessions[0].kind == "background"
    assert sessions[1].session_id == "a65e24bb-eda1-4294-8ad0-b39f3cf8891d"
    assert sessions[1].cwd == "/home/lukas/DEV"
    assert sessions[1].status == "busy"
    assert sessions[0].pid == 1280934
    assert sessions[0].state == "blocked"
    assert sessions[1].pid == 1611743
    assert sessions[1].state is None


def test_discover_sessions_empty_on_nonzero_exit():
    fake_result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=fake_result):
        assert discover_sessions() == []


def test_discover_sessions_empty_on_garbage_output():
    fake_result = MagicMock(returncode=0, stdout="not json")
    with patch("subprocess.run", return_value=fake_result):
        assert discover_sessions() == []


def test_discover_sessions_empty_when_claude_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        assert discover_sessions() == []


def _session(status="idle", state=None):
    return DiscoveredSession(
        session_id="s1", name="n", cwd="/tmp", kind="interactive", status=status, pid=1, state=state
    )


def test_session_ready_for_input_true_when_idle_and_not_blocked():
    assert session_ready_for_input(_session(status="idle", state=None)) is True


def test_session_ready_for_input_false_when_busy():
    assert session_ready_for_input(_session(status="busy", state=None)) is False


def test_session_ready_for_input_false_when_blocked_even_if_status_idle():
    assert session_ready_for_input(_session(status="idle", state="blocked")) is False


def test_find_tmux_pane_for_pid_matches_by_ppid():
    ppid_result = MagicMock(returncode=0, stdout="1282101\n")
    panes_result = MagicMock(
        returncode=0,
        stdout="1:0.0 1280281\n1:0.1 1381393\n1:0.2 1282101\n1:0.3 1289216\n",
    )
    with patch("subprocess.run", side_effect=[ppid_result, panes_result]):
        assert find_tmux_pane_for_pid(1611743) == "1:0.2"


def test_find_tmux_pane_for_pid_no_match_returns_none():
    ppid_result = MagicMock(returncode=0, stdout="99999\n")
    panes_result = MagicMock(returncode=0, stdout="1:0.0 1280281\n")
    with patch("subprocess.run", side_effect=[ppid_result, panes_result]):
        assert find_tmux_pane_for_pid(1611743) is None


def test_find_tmux_pane_for_pid_process_gone_returns_none():
    ppid_result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=ppid_result):
        assert find_tmux_pane_for_pid(999999) is None
