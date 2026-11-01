import json

import pytest

from ccc import plugins
from ccc.launch_options import (
    DEFAULT_SELECTION, PLUGINS_SELECT, describe_flags, is_plugin, persistent_flags, toggle,
)


@pytest.fixture
def claude_dir(tmp_path, monkeypatch):
    (tmp_path / "plugins").mkdir()
    (tmp_path / "plugins" / "installed_plugins.json").write_text(json.dumps(
        {"plugins": {"a@m": [{}], "b@m": [{}], "c@m": [{}]}}))
    (tmp_path / "settings.json").write_text(json.dumps(
        {"enabledPlugins": {"a@m": True, "b@m": False, "gone@m": True}}))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CCC_MCP_DIR", str(tmp_path / "cfg"))
    return tmp_path


def test_installed_and_default(claude_dir):
    assert plugins.installed() == ["a@m", "b@m", "c@m"]
    assert plugins.enabled_by_default() == ["a@m"]  # b off, gone not installed


def test_no_marker_inherits(claude_dir):
    assert plugins.resolve_flags(["--model", "opus"]) == ["--model", "opus"]
    assert plugins.resolve_flags(None) is None


def test_marker_becomes_settings_switching_every_installed_plugin(claude_dir):
    out = plugins.resolve_flags(["--model", "opus", "--ccc-plugins=b@m,missing@m"])
    assert out[:2] == ["--model", "opus"] and out[2] == "--settings"
    assert json.loads(open(out[3]).read()) == {"enabledPlugins": {"a@m": False, "b@m": True, "c@m": False}}


def test_empty_marker_disables_all(claude_dir):
    out = plugins.resolve_flags(["--ccc-plugins="])
    assert set(json.loads(open(out[1]).read())["enabledPlugins"].values()) == {False}


def test_selection_roundtrip():
    sel = toggle(DEFAULT_SELECTION, "plugin:a@m", True)
    assert PLUGINS_SELECT in sel and is_plugin("plugin:a@m")
    flags = persistent_flags(sel)
    assert "--ccc-plugins=a@m" in flags
    assert "a" in describe_flags(flags)
    assert not any(k.startswith("plugin:") for k in toggle(sel, PLUGINS_SELECT, False))
    assert not any(f.startswith("--ccc-plugins") for f in persistent_flags(DEFAULT_SELECTION))
