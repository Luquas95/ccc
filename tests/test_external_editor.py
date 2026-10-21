import stat
import subprocess
import sys

import pytest
from textual.app import App
from textual.widgets import Input, TextArea

from ccc import external_editor
from ccc.external_editor import BY_ID, command, edit, installed
from ccc.storage import Storage


def _fake_editor(tmp_path, body: str):
    """A Python "editor" running body with the file in `path`."""
    script = tmp_path / "fake_editor.py"
    script.write_text("import sys, pathlib\npath = pathlib.Path(sys.argv[1])\n" + body)
    return (sys.executable, str(script))


def test_edit_returns_the_saved_text_with_diacritics_and_blank_lines(tmp_path):
    argv = _fake_editor(tmp_path, "path.write_text(path.read_text() + '\\n\\nŽluťoučký kůň\\n\\n', encoding='utf-8')\n")
    assert edit(argv, "Ahoj", tmp_path / "ccc") == "Ahoj\n\nŽluťoučký kůň\n"
    assert list((tmp_path / "ccc").iterdir()) == []  # the file is gone


def test_edit_drops_only_the_newline_the_editor_adds(tmp_path):
    argv = _fake_editor(tmp_path, "path.write_text('one\\n')\n")
    assert edit(argv, "two", tmp_path) == "one"
    assert edit(argv, "two\n", tmp_path) == "one\n"


def test_closed_without_saving_or_failing_changes_nothing(tmp_path):
    assert edit(_fake_editor(tmp_path, "pass\n"), "same", tmp_path) is None
    assert edit(_fake_editor(tmp_path, "path.write_text('x'); sys.exit(1)\n"), "same", tmp_path) is None


def test_file_is_private_to_you(tmp_path):
    seen = {}

    def run(args):
        seen["mode"] = stat.S_IMODE((tmp_path / args[-1]).stat().st_mode)
        seen["dir"] = (tmp_path / args[-1]).parent
        return subprocess.CompletedProcess(args, 0)

    edit(("ed",), "t", tmp_path, run=run)
    assert seen["mode"] == 0o600 and seen["dir"] == tmp_path


def _path_with(tmp_path, monkeypatch, *names):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name in names:
        exe = bin_dir / name
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))


def test_installed_lists_only_editors_in_path_gui_only_with_a_display(tmp_path, monkeypatch):
    _path_with(tmp_path, monkeypatch, "vim", "code")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert [e.id for e in installed()] == ["vim"]
    monkeypatch.setenv("DISPLAY", ":0")
    assert [e.id for e in installed()] == ["vim", "code"]


def test_command_setting_then_environment_then_first_installed(tmp_path, monkeypatch):
    _path_with(tmp_path, monkeypatch, "nano", "vim", "micro")
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)
    storage = Storage(tmp_path / "h.db")
    assert command(storage) == ("nano",)
    monkeypatch.setenv("EDITOR", "vim -u NONE")
    assert command(storage) == ("vim", "-u", "NONE")
    monkeypatch.setenv("VISUAL", "micro")
    assert command(storage) == ("micro",)
    storage.set_setting(external_editor.SETTING_KEY, "nano")
    assert command(storage) == BY_ID["nano"].argv
    storage.set_setting(external_editor.SETTING_KEY, "hx")  # not installed any more
    assert command(storage) == ("micro",)
    monkeypatch.setenv("VISUAL", "not-here")
    monkeypatch.delenv("EDITOR")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert command(storage) is None


@pytest.mark.asyncio
async def test_ctrl_e_puts_the_saved_text_back_into_the_focused_box(tmp_path, monkeypatch):
    from contextlib import nullcontext

    from ccc.tui.app import CCContinueApp

    storage_path = tmp_path / "h.db"
    Storage(storage_path)
    calls = []

    def fake_edit(argv, text, folder):
        calls.append((argv, text, folder))
        return text + "\nfrom the editor"

    monkeypatch.setattr("ccc.external_editor.command", lambda storage: ("nano",))
    monkeypatch.setattr("ccc.external_editor.edit", fake_edit)

    class Host(CCContinueApp):
        def initial_screens(self):
            return []

        def compose(self):
            yield TextArea("draft", id="box")
            yield Input(id="line")

    app = Host(str(storage_path))
    monkeypatch.setattr(app, "suspend", lambda: nullcontext())
    async with app.run_test() as pilot:
        app.query_one("#box").focus()
        await pilot.press("ctrl+e")
        await pilot.pause()
        assert app.query_one("#box", TextArea).text == "draft\nfrom the editor"
        assert calls == [(("nano",), "draft", tmp_path)]
        # Not a text box: Ctrl+E is the field's own (end of line), no editor.
        line = app.query_one("#line", Input)
        line.value = "abc"
        line.focus()
        line.cursor_position = 0
        await pilot.press("ctrl+e")
        assert len(calls) == 1 and line.cursor_position == 3
