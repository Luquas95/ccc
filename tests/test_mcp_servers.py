import json
from pathlib import Path

import pytest

from ccc import mcp_servers
from ccc.launch_options import (
    DEFAULT_SELECTION, MCP_SELECT, describe_flags, is_mcp_server, persistent_flags, toggle,
)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    (tmp_path / "cfg").mkdir()
    return tmp_path / "cfg"


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_discover_merges_user_project_and_local_servers(home, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    _write(home / ".claude.json", {
        "mcpServers": {"context7": {"type": "http", "url": "u"}, "shared": {"command": "user"}},
        "projects": {str(project): {
            "mcpServers": {"shared": {"command": "local"}, "playwright": {"command": "p"}},
            "enabledMcpjsonServers": ["shared", "db"],
        }},
    })
    _write(project / ".mcp.json", {"mcpServers": {"shared": {"command": "project"}, "db": {"command": "d"}}})

    found = mcp_servers.discover(str(project))

    assert sorted(found) == ["context7", "db", "playwright", "shared"]
    assert found["shared"] == {"command": "local"}  # local beats project beats user
    assert mcp_servers.names(str(project)) == ["context7", "db", "playwright", "shared"]


def test_project_servers_need_the_users_approval(home, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    _write(project / ".mcp.json", {"mcpServers": {"evil": {"command": "rm"}, "ok": {"command": "x"}, "off": {"command": "y"}}})
    assert mcp_servers.names(str(project)) == []  # nothing approved: the repository alone decides nothing

    _write(home / ".claude.json", {"projects": {str(project): {
        "enabledMcpjsonServers": ["ok", "off"], "disabledMcpjsonServers": ["off"]}}})
    assert mcp_servers.names(str(project)) == ["ok"]

    _write(home / ".claude.json", {})
    _write(home / "settings.json", {"enableAllProjectMcpServers": True})
    assert mcp_servers.names(str(project)) == ["evil", "off", "ok"]  # the user's own settings approve all


def test_a_rejection_in_either_place_wins(home, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    _write(project / ".mcp.json", {"mcpServers": {"a": {"command": "x"}, "b": {"command": "y"}}})
    _write(home / ".claude.json", {"projects": {str(project): {"enabledMcpjsonServers": ["a", "b"]}}})
    _write(home / "settings.json", {"disabledMcpjsonServers": ["b"]})
    assert mcp_servers.names(str(project)) == ["a"]


def test_a_remembered_choice_does_not_run_an_unapproved_project_server(home, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    _write(project / ".mcp.json", {"mcpServers": {"db": {"command": "rm"}}})
    assert mcp_servers.resolve_flags(["--ccc-mcp=db"], str(project)) == ["--strict-mcp-config"]


def test_discover_survives_missing_or_broken_files(home, tmp_path):
    assert mcp_servers.discover(str(tmp_path)) == {}
    (home / ".claude.json").write_text("not json")
    (tmp_path / ".mcp.json").write_text('{"mcpServers": [1]}')
    assert mcp_servers.discover(str(tmp_path)) == {}


def test_our_own_server_and_odd_names_are_not_offered(home, tmp_path):
    _write(home / ".claude.json", {"mcpServers": {"ccc": {}, "a,b": {}, "x=y": {}, "ok": {}}})
    assert mcp_servers.names(str(tmp_path)) == ["ok"]


def test_selection_becomes_a_marker_flag_with_names_only():
    sel = toggle(toggle(DEFAULT_SELECTION, "mcp:context7", True), "mcp:codegraph", True)
    assert MCP_SELECT in sel  # ticking a server turns the mode on
    assert persistent_flags(sel) == ["--dangerously-skip-permissions", "--ccc-mcp=codegraph,context7"]


def test_mode_without_servers_means_none_and_unticking_the_mode_forgets_servers():
    sel = toggle(DEFAULT_SELECTION, MCP_SELECT, True)
    assert persistent_flags(sel)[-1] == "--ccc-mcp="
    sel = toggle(toggle(sel, "mcp:context7", True), MCP_SELECT, False)
    assert not any(is_mcp_server(k) for k in sel) and MCP_SELECT not in sel
    assert persistent_flags(sel) == ["--dangerously-skip-permissions"]


def test_default_selection_adds_no_mcp_flag():
    assert not any(f.startswith("--ccc-mcp") for f in persistent_flags(DEFAULT_SELECTION))


def test_describe_flags():
    assert describe_flags(["--ccc-mcp=a,b", "--model", "haiku"]) == "Haiku · MCP: a, b"
    assert describe_flags(["--ccc-mcp="]) == "MCP: none"


def test_resolve_flags_without_marker_is_unchanged(home, tmp_path):
    assert mcp_servers.resolve_flags(None, str(tmp_path)) is None
    flags = ["--model", "haiku"]
    assert mcp_servers.resolve_flags(flags, str(tmp_path)) == flags


def test_resolve_flags_hands_over_only_the_chosen_servers(home, tmp_path):
    _write(home / ".claude.json", {"mcpServers": {"a": {"command": "x", "env": {"T": "secret"}}, "b": {"command": "y"}}})

    flags = mcp_servers.resolve_flags(["--model", "haiku", "--ccc-mcp=a,gone"], str(tmp_path))

    assert flags[:3] == ["--model", "haiku", "--strict-mcp-config"]
    assert flags[3] == "--mcp-config"
    assert len(flags) == 5
    assert "secret" not in " ".join(flags)  # the definitions never go on the command line
    path = Path(flags[4])
    assert json.loads(path.read_text()) == {"mcpServers": {"a": {"command": "x", "env": {"T": "secret"}}}}
    assert path.stat().st_mode & 0o777 == 0o600 and path.parent.stat().st_mode & 0o777 == 0o700
    assert mcp_servers.resolve_flags(["--ccc-mcp=a"], str(tmp_path))[2] == str(path)  # same choice, same file


def test_resolve_flags_for_none_is_strict_without_servers(home, tmp_path):
    assert mcp_servers.resolve_flags(["--ccc-mcp="], str(tmp_path)) == ["--strict-mcp-config"]
