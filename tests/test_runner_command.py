from ccc.runner import build_command


def test_legacy_queue_command_unchanged():
    assert build_command("sid", "hi", False) == [
        "claude", "--session-id", "sid", "-p", "hi", "--output-format", "json", "--dangerously-skip-permissions",
    ]
    assert build_command("sid", "hi", True)[1:3] == ["--resume", "sid"]


def test_launch_flags_replace_legacy_permission_flag():
    cmd = build_command("sid", "hi", True, ["--permission-mode", "plan", "--model", "haiku"])
    assert "--dangerously-skip-permissions" not in cmd
    assert cmd[-4:] == ["--permission-mode", "plan", "--model", "haiku"]


def test_first_run_flags_that_pick_the_session_drop_own_session_flag():
    cmd = build_command("placeholder", "hi", False, [], ["--resume", "orig", "--fork-session"])
    assert cmd[:4] == ["claude", "--resume", "orig", "--fork-session"]
    assert "placeholder" not in cmd
    cmd = build_command("placeholder", "hi", False, [], ["--from-pr", "42"])
    assert cmd[:3] == ["claude", "--from-pr", "42"] and "placeholder" not in cmd


async def test_execute_gives_permission_tool_a_long_mcp_timeout(monkeypatch):
    import asyncio

    from ccc import runner

    seen = {}

    class FakeProc:
        returncode = 0

        async def communicate(self):
            return b'{"is_error": false, "result": "ok", "session_id": "s"}', b""

    async def fake_exec(*args, cwd=None, stdout=None, stderr=None, env=None):
        seen["env"] = env
        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    await runner.execute("/tmp", "s", "hi", False, ["--permission-prompt-tool", "mcp__ccc__approve"])
    assert int(seen["env"]["MCP_TOOL_TIMEOUT"]) >= 7 * 24 * 3600 * 1000
    await runner.execute("/tmp", "s", "hi", False, ["--model", "haiku"])
    assert seen["env"] is None or "MCP_TOOL_TIMEOUT" not in seen["env"]
