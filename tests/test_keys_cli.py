import argparse
import json

import pytest

from ccc import keymap, keys_cli
from ccc.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "h.db")


def _args(*argv):
    parser = argparse.ArgumentParser()
    keys_cli.add_parser(parser.add_subparsers(dest="command"))
    return parser.parse_args(["keys", *argv])


def test_list(storage, capsys):
    assert keys_cli.run(storage, _args("list")) == 0
    assert "views.analytics" in capsys.readouterr().out


def test_check_free_and_taken(storage, capsys):
    assert keys_cli.run(storage, _args("check", "F5")) == 0
    assert "F5 is free" in capsys.readouterr().out
    assert keys_cli.run(storage, _args("check", "d")) == 1
    assert "already “Dashboard”" in capsys.readouterr().out
    assert keys_cli.run(storage, _args("check", "ctrl+t", "app.screenshot")) == 1
    assert "Claude Code key" in capsys.readouterr().out


def test_set_refuses_a_collision(storage, capsys):
    assert keys_cli.run(storage, _args("set", "views.analytics", "d")) == 1
    assert keymap.load(storage) == {}
    assert keys_cli.run(storage, _args("set", "views.analytics", "F5")) == 0
    assert keymap.load(storage) == {"views.analytics": "f5"}


def test_reset_one_or_all(storage):
    keymap.save(storage, {**keymap.defaults(), "views.analytics": "f5", "app.screenshot": "f6"})
    assert keys_cli.run(storage, _args("reset", "views.analytics")) == 0
    assert keymap.load(storage) == {"app.screenshot": "f6"}
    assert keys_cli.run(storage, _args("reset")) == 0
    assert keymap.load(storage) == {}


def test_unknown_action_and_key_stop_with_a_message(storage):
    with pytest.raises(SystemExit, match="Unknown action"):
        keys_cli.run(storage, _args("set", "nope", "f5"))
    with pytest.raises(SystemExit, match="isn't a key"):
        keys_cli.run(storage, _args("set", "views.analytics", "hyper+x"))


def test_export_then_import(storage, tmp_path):
    keymap.save(storage, {**keymap.defaults(), "app.screenshot": "f6"})
    assert keys_cli.run(storage, _args("export", str(tmp_path / "out"))) == 0
    keymap.save(storage, keymap.defaults())
    assert keys_cli.run(storage, _args("import", str(tmp_path / "out"))) == 0
    assert keymap.load(storage) == {"app.screenshot": "f6"}


def test_import_with_collisions_changes_nothing(storage, tmp_path, capsys):
    path = tmp_path / "k.json"
    path.write_text(json.dumps({"format": "ccc-keys", "version": 1, "keys": {"views.analytics": "d"}}))
    assert keys_cli.run(storage, _args("import", str(path))) == 1
    assert "collide" in capsys.readouterr().out
    assert keymap.load(storage) == {}
