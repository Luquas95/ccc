"""ccc's own lines have the colour of the tmux frame: where the keys go."""
import subprocess

import pytest
from textual.color import Color

from ccc.tui import cli_pane, theme
from ccc.tui.app import CCContinueApp


def test_frame_colour_follows_where_the_keys_go():
    assert theme.frame_variables("claude")["ccc-frame"] == theme.FRAME_CLAUDE
    assert theme.frame_variables("ccc")["ccc-frame"] == theme.FRAME_CCC
    # No tmux frame (plain terminal, a foreign tmux): the quiet line colour.
    assert theme.frame_variables(None)["ccc-frame"] == theme.VARIABLES["ccc-line"] == "#3a3a3a"
    assert theme.frame_variables(None) is theme.VARIABLES


def test_tmux_and_ccc_use_the_same_two_colours():
    # tmux's colourN and Textual's hex are one colour of the 256 cube.
    def cube(n):
        n -= 16
        return "#" + "".join(f"{(0 if c == 0 else 55 + 40 * c):02x}" for c in (n // 36, n // 6 % 6, n % 6))

    assert cube(int(theme.TMUX_FRAME_CLAUDE.removeprefix("colour"))) == theme.FRAME_CLAUDE
    assert cube(int(theme.TMUX_FRAME_CCC.removeprefix("colour"))) == theme.FRAME_CCC


def _list_panes(output):
    return lambda *args: subprocess.CompletedProcess(args, 0, output, "")


@pytest.mark.parametrize("panes, expected", [
    ("1 \n0 4\n0 \n", False),   # ccc active
    ("0 \n1 4\n0 \n", True),    # Claude Code active
    ("0 \n0 4\n1 \n", False),   # the key strip / bar active
    ("1 \n", False),            # no Claude Code pane
])
def test_keys_in_claude(monkeypatch, panes, expected):
    monkeypatch.setenv("TMUX_PANE", "%0")
    monkeypatch.setattr(cli_pane, "_tmux", _list_panes(panes))
    assert cli_pane.keys_in_claude() is expected


@pytest.mark.asyncio
async def test_lines_change_colour_with_the_keys(tmp_path):
    app = CCContinueApp(str(tmp_path / "history.db"))
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        sidebar = app.screen.query_one("#sidebar")
        assert sidebar.styles.border_right[1] == Color.parse(theme.VARIABLES["ccc-line"])  # not in tmux
        app.set_keys_in("claude")
        await pilot.pause()
        assert app.get_css_variables()["ccc-frame"] == theme.FRAME_CLAUDE
        assert sidebar.styles.border_right[1].hex[:7].lower() == theme.FRAME_CLAUDE
        app.set_keys_in("ccc")
        await pilot.pause()
        assert sidebar.styles.border_right[1].hex[:7].lower() == theme.FRAME_CCC
