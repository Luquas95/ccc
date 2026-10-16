import subprocess

import pytest

from ccc.tui import cli_pane


class FakeTmux:
    """Records tmux calls; panes: {pane_id: queue id or ""}."""

    def __init__(self, panes=None, width=200):
        self.calls = []
        self.panes = panes if panes is not None else {"%0": ""}
        self.width = width

    def __call__(self, *args):
        self.calls.append(args)
        out, code = "", 0
        if args[0] == "list-panes":
            out = "\n".join(f"{p} {q}" for p, q in self.panes.items())
        elif args[0] == "display-message":
            out = str(self.width)
        elif args[0] == "split-window":
            pane = f"%{len(self.panes)}"
            self.panes[pane] = ""
            out = pane
        elif args[0] == "set-option" and args[1] == "-p" and args[4] == "@ccc-cli":
            self.panes[args[3]] = args[5]
        elif args[0] == "kill-pane":
            self.panes.pop(args[2], None)
        return subprocess.CompletedProcess(args, code, out + "\n", "")


@pytest.fixture
def tmux(monkeypatch):
    fake = FakeTmux()
    monkeypatch.setattr(cli_pane, "_tmux", fake)
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/ccc,123,0")
    monkeypatch.setenv("TMUX_PANE", "%0")
    return fake


def test_available_only_inside_tmux(monkeypatch):
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    assert not cli_pane.available()
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/ccc,1,0")
    monkeypatch.setenv("TMUX_PANE", "%0")
    assert cli_pane.available()


def test_open_splits_next_to_ccc_keeping_the_sidebar(tmux):
    pane = cli_pane.open(4)
    split = next(c for c in tmux.calls if c[0] == "split-window")
    assert split[split.index("-l") + 1] == str(200 - cli_pane.SIDEBAR_COLUMNS - 1)
    assert split[-1].endswith("-m ccc.attach_cli 4")
    assert "-d" in split  # ccc keeps the keyboard until focus()
    assert cli_pane.find() == (pane, 4)
    assert ("set-option", "-t", "%0", "mouse", "on") in tmux.calls
    # You can see which pane you type in, and what each one is.
    assert ("set-option", "-w", "-t", "%0", "pane-border-status", "top") in tmux.calls
    assert ("set-option", "-p", "-t", "%0", "@ccc-title", "ccc") in tmux.calls


def test_open_titles_the_pane_with_the_conversation(tmux):
    pane = cli_pane.open(4, "Kompas")
    assert ("set-option", "-p", "-t", pane, "@ccc-title", "Claude Code · Kompas") in tmux.calls


def test_open_switches_the_existing_pane(tmux):
    pane = cli_pane.open(4)
    tmux.calls.clear()
    assert cli_pane.open(9) == pane
    assert tmux.calls[1][:4] == ("respawn-pane", "-k", "-t", pane)
    assert cli_pane.find() == (pane, 9)
    tmux.calls.clear()
    cli_pane.open(9)  # already shown: nothing restarted
    assert not any(c[0] in ("respawn-pane", "split-window") for c in tmux.calls)


def test_mouse_left_alone_on_a_foreign_tmux(tmux, monkeypatch):
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,123,0")
    cli_pane.open(4)
    assert not any(c[0] == "set-option" and ("mouse" in c or "pane-border-status" in c) for c in tmux.calls)


def test_focus_zooms_on_narrow_windows(tmux):
    pane = cli_pane.open(4)
    cli_pane.focus()
    assert ("select-pane", "-t", pane) in tmux.calls
    assert not any(c[0] == "resize-pane" for c in tmux.calls)
    tmux.width = 80
    cli_pane.focus()
    assert ("resize-pane", "-Z", "-t", pane) in tmux.calls


def test_close_kills_only_the_cli_pane(tmux):
    cli_pane.close()  # nothing open: nothing killed
    assert not any(c[0] == "kill-pane" for c in tmux.calls)
    pane = cli_pane.open(4)
    cli_pane.close()
    assert ("kill-pane", "-t", pane) in tmux.calls
    assert cli_pane.find() is None
