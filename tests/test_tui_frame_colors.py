"""The frame is green everywhere: tmux's lines and ccc's own."""
import pytest
from textual.color import Color

from ccc.tui import cli_pane, theme
from ccc.tui.app import CCContinueApp


def test_tmux_and_ccc_use_the_same_green():
    # tmux's colourN and Textual's hex are one colour of the 256 cube.
    n = int(theme.TMUX_FRAME.removeprefix("colour")) - 16
    cube = "#" + "".join(f"{(0 if c == 0 else 55 + 40 * c):02x}" for c in (n // 36, n // 6 % 6, n % 6))
    assert cube == theme.FRAME == theme.VARIABLES["ccc-frame"]


@pytest.mark.asyncio
async def test_menu_is_a_rounded_block_without_tmux_and_gives_way_to_its_frame(tmp_path):
    app = CCContinueApp(str(tmp_path / "history.db"))
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        sidebar = app.screen.query_one("#sidebar")
        green = Color.parse(theme.FRAME)
        # Plain terminal: its own rounded block on all four sides.
        assert {sidebar.styles.border_top[0], sidebar.styles.border_right[0],
                sidebar.styles.border_bottom[0], sidebar.styles.border_left[0]} == {"round"}
        assert sidebar.styles.border_right[1] == green
        # In ccc's tmux the top and bottom are tmux's; the menu adds its left
        # line and a right one to Claude Code…
        app.screen.add_class("-tmux-frame")
        app.refresh_css(animate=False)
        await pilot.pause()
        assert sidebar.styles.border_right[0] == "solid" and sidebar.styles.border_left[0] == "solid"
        assert sidebar.styles.border_top[0] == "" and sidebar.styles.border_bottom[0] == ""
        # …and none while Claude Code is open (tmux draws that one).
        app.screen.add_class("-cli-open")
        app.refresh_css(animate=False)
        await pilot.pause()
        assert sidebar.styles.border_right[0] == "" and sidebar.styles.border_left[0] == "solid"


def test_key_list_keeps_textuals_blue_on_the_black_theme():
    variables = theme.THEME.to_color_system().generate()
    assert variables["footer-background"].upper() == "#242F38"
    assert variables["background"] == "#000000" and variables["surface"] == "#000000"
