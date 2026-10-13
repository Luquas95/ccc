from unittest.mock import MagicMock, patch

from ccc.live_delivery import deliver_to_live_session
from ccc.session_discovery import DiscoveredSession


def _session(status="idle", state=None, pid=1611743, sid="target-sid"):
    return DiscoveredSession(
        session_id=sid, name="dev-75", cwd="/home/lukas/DEV", kind="interactive", status=status, pid=pid, state=state
    )


def test_delivers_when_session_ready():
    text_result = MagicMock(returncode=0, stderr="")
    enter_result = MagicMock(returncode=0, stderr="")
    with (
        patch("ccc.live_delivery.discover_sessions", return_value=[_session()]),
        patch("ccc.live_delivery.find_tmux_pane_for_pid", return_value="1:0.2"),
        patch("subprocess.run", side_effect=[text_result, enter_result]) as mock_run,
    ):
        result = deliver_to_live_session("target-sid", "ahoj")

    assert result.delivered is True
    assert result.error is None
    first_call_args = mock_run.call_args_list[0][0][0]
    assert first_call_args == ["tmux", "send-keys", "-t", "1:0.2", "-l", "ahoj"]
    second_call_args = mock_run.call_args_list[1][0][0]
    assert second_call_args == ["tmux", "send-keys", "-t", "1:0.2", "Enter"]


def test_session_not_found():
    with patch("ccc.live_delivery.discover_sessions", return_value=[]):
        result = deliver_to_live_session("target-sid", "ahoj")
    assert result.delivered is False
    assert "no longer running" in result.error


def test_session_busy_not_delivered():
    with patch("ccc.live_delivery.discover_sessions", return_value=[_session(status="busy")]):
        result = deliver_to_live_session("target-sid", "ahoj")
    assert result.delivered is False
    assert "not ready" in result.error


def test_session_blocked_not_delivered():
    with patch("ccc.live_delivery.discover_sessions", return_value=[_session(state="blocked")]):
        result = deliver_to_live_session("target-sid", "ahoj")
    assert result.delivered is False
    assert "not ready" in result.error


def test_pane_not_found():
    with (
        patch("ccc.live_delivery.discover_sessions", return_value=[_session()]),
        patch("ccc.live_delivery.find_tmux_pane_for_pid", return_value=None),
    ):
        result = deliver_to_live_session("target-sid", "ahoj")
    assert result.delivered is False
    assert "pane" in result.error


def test_send_keys_failure_surfaces_error():
    text_result = MagicMock(returncode=1, stderr="can't find pane")
    with (
        patch("ccc.live_delivery.discover_sessions", return_value=[_session()]),
        patch("ccc.live_delivery.find_tmux_pane_for_pid", return_value="1:0.2"),
        patch("subprocess.run", return_value=text_result),
    ):
        result = deliver_to_live_session("target-sid", "ahoj")
    assert result.delivered is False
    assert "can't find pane" in result.error
