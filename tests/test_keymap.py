import json

import pytest

from ccc import keymap
from ccc.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "h.db")


def test_defaults_are_free_of_collisions():
    assert keymap.check(keymap.defaults()) == {}


@pytest.mark.parametrize("text,key", [
    ("Ctrl+P", "ctrl+p"), ("alt+s", "alt+s"), ("+", "plus"), ("?", "question_mark"), ("F5", "f5"),
    ("Esc", "escape"), ("Ctrl+]", "ctrl+right_square_bracket"), ("Del", "delete"), ("ctrl+↑", "ctrl+up"),
    ("Control+Shift+X", "ctrl+shift+x"), ("A", "A"),
])
def test_parse(text, key):
    assert keymap.parse(text) == key


@pytest.mark.parametrize("text", ["", "ctrl+", "x+y", "hyper+a", "ctrl+ctrl+a", "nonsense"])
def test_parse_rejects(text):
    assert keymap.parse(text) is None


def test_pretty_and_tmux_names():
    assert [keymap.pretty(k) for k in ("ctrl+p", "alt+s", "plus", "question_mark", "f5")] == \
        ["Ctrl+P", "Alt+S", "+", "?", "F5"]
    assert [keymap.tmux_key(k) for k in ("ctrl+p", "alt+s", "alt+0", "ctrl+right_square_bracket", "f5")] == \
        ["C-p", "M-s", "M-0", "C-]", "F5"]


def _problems(action_id, key):
    return keymap.problems(action_id, key, keymap.defaults())


def test_same_key_where_both_work_collides():
    assert "already “Dashboard”" in " ".join(_problems("views.analytics", "d"))
    # Ctrl+P (Settings) works in every window too.
    assert "already “Settings”" in " ".join(_problems("tasks.add", "ctrl+p"))


def test_same_key_in_separate_places_is_fine():
    # The task editor's keys only work while it's open.
    assert _problems("tasks.add", "c") == []
    assert _problems("views.analytics", "f5") == []


def test_keys_the_terminal_or_tmux_take_are_refused():
    assert "Tab" in " ".join(_problems("views.analytics", "ctrl+i"))
    assert "prefix" in " ".join(_problems("views.analytics", "ctrl+b"))


def test_list_and_text_keys_only_as_their_own_default():
    assert _problems("views.analytics", "up") != []
    assert _problems("analytics.prev", "left") == []


def test_keys_working_from_claude_code_must_not_take_its_keys():
    assert "Claude Code key" in " ".join(_problems("app.screenshot", "ctrl+t"))
    assert "needs Ctrl or Alt" in " ".join(_problems("app.screenshot", "x"))
    assert _problems("app.screenshot", "f6") == []
    # Keys that only work in ccc may use Claude Code's (Ctrl+T reaches ccc
    # only while ccc has the keyboard).
    assert _problems("conversations.tasks", "ctrl+t") == []


def test_unknown_keys_are_refused():
    assert "isn't a key" in " ".join(_problems("views.analytics", "hyper+x"))


def test_save_keeps_only_changes_and_refuses_collisions(storage):
    keymap.save(storage, {**keymap.defaults(), "views.analytics": "f5"})
    assert json.loads(storage.get_setting(keymap.SETTING_KEY)) == {"views.analytics": "f5"}
    assert keymap.key_of(storage, "views.analytics") == "f5"
    with pytest.raises(keymap.KeymapError) as error:
        keymap.save(storage, {**keymap.defaults(), "views.analytics": "d"})
    assert "views.analytics" in error.value.problems
    assert keymap.key_of(storage, "views.analytics") == "f5"  # unchanged


def test_a_broken_setting_means_defaults(storage):
    storage.set_setting(keymap.SETTING_KEY, "{not json")
    assert keymap.current(storage) == keymap.defaults()
    storage.set_setting(keymap.SETTING_KEY, json.dumps({"nope": "x", "views.analytics": 5}))
    assert keymap.load(storage) == {}


def test_export_and_import(tmp_path):
    keys = {**keymap.defaults(), "app.screenshot": "f6"}
    path = keymap.export(keys, tmp_path / "out")
    assert path == tmp_path / "out" / keymap.EXPORT_NAME
    assert keymap.read_export(tmp_path / "out") == keys  # the folder…
    assert keymap.read_export(path) == keys  # …or the file


def test_import_accepts_written_key_names_and_skips_unknown_ids(tmp_path):
    path = tmp_path / "k.json"
    path.write_text(json.dumps({"format": "ccc-keys", "version": 1,
                                "keys": {"app.screenshot": "F6", "gone.action": "x"}}))
    assert keymap.read_export(path)["app.screenshot"] == "f6"


@pytest.mark.parametrize("content", ["not json", json.dumps({"keys": {}}), json.dumps([1])])
def test_import_refuses_other_files(tmp_path, content):
    path = tmp_path / "k.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        keymap.read_export(path)


def test_import_of_a_missing_file_says_so(tmp_path):
    with pytest.raises(ValueError, match="Can't read"):
        keymap.read_export(tmp_path / "missing.json")
