import json
from unittest.mock import MagicMock, patch

from cc_continue.session_discovery import discover_sessions

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
