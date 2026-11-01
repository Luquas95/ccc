from rich.console import Console
from textual.scrollbar import ScrollBar

from ccc.tui import scrollbar


def _segments(position=40, height=10):
    render = scrollbar.GreenScrollBarRender(
        virtual_size=100, window_size=20, position=position, vertical=True
    )
    console = Console(width=scrollbar.WIDTH, height=height, force_terminal=True, color_system="truecolor")
    return [s for s in render.__rich_console__(console, console.options.update(height=height)) if s.text != "\n"]


def test_install_replaces_the_renderer():
    original = ScrollBar.renderer
    try:
        scrollbar.install()
        assert ScrollBar.renderer is scrollbar.GreenScrollBarRender
    finally:
        ScrollBar.renderer = original


def test_thumb_is_green_with_light_top_and_dark_bottom_line():
    segs = _segments()
    faces = [s for s in segs if s.style.bgcolor.triplet == (0, 0xAA, 0)]
    assert faces, "the thumb face must be #00aa00"
    glyphs = [s.text for s in faces]
    assert glyphs[0] == "▔" and glyphs[-1] == "▁"
    assert faces[0].style.color.triplet == scrollbar.HI
    assert faces[-1].style.color.triplet == scrollbar.LO


def test_track_cells_scroll_and_thumb_grabs():
    segs = _segments(position=40)
    metas = {s.style.meta["@mouse.down"] for s in segs}
    assert metas == {"scroll_up", "grab", "scroll_down"}


def test_no_thumb_when_everything_fits():
    render = scrollbar.GreenScrollBarRender(virtual_size=10, window_size=10, position=0, vertical=True)
    console = Console(width=2, height=10, force_terminal=True, color_system="truecolor")
    segs = [s for s in render.__rich_console__(console, console.options.update(height=10)) if s.text != "\n"]
    assert all(s.style.bgcolor.triplet == scrollbar.TRACK for s in segs)
