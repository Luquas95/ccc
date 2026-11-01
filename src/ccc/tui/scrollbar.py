"""The app's main scrollbar: a green 3D (bevelled) thumb on a flat track.

Taken from item 513 of the scrollbar gallery (DEV/pytemp/posuvniky_demo.py):
shape 5 = narrow thumb, track 1 = flat. Recoloured to #00aa00 and drawn like the
green 3D buttons (layout.py): solid face, thin light top line, thin dark bottom line.
Installed for every scrollbar by `install()`.
"""
from __future__ import annotations

from rich.color import Color
from rich.segment import Segment
from rich.style import Style
from textual.scrollbar import ScrollBar, ScrollBarRender

RGB = tuple[int, int, int]

WIDTH = 2
BASE: RGB = (0, 0xAA, 0)  # #00aa00
HI: RGB = (0x5F, 0xD7, 0x5F)  # light top/left edge, as on the 3D buttons (#5fd75f)
LO: RGB = (0, 0x5F, 0)  # dark bottom/right edge (#005f00)
TRACK: RGB = (4, 20, 4)


def _color(rgb: RGB) -> Color:
    return Color.from_rgb(*rgb)


def thumb_cell(row: int, n: int, col: int) -> tuple[str, RGB | None, RGB]:
    """(glyph, foreground, background) of one thumb cell; the thumb is n rows tall.

    Like a `tall` button border: a solid face with a thin light line along the
    top and a thin dark line along the bottom.
    """
    if row == 0:
        return ("▔", HI, BASE)
    if row == n - 1:
        return ("▁", LO, BASE)
    return (" ", None, BASE)


class GreenScrollBarRender(ScrollBarRender):
    def __rich_console__(self, console, options):  # noqa: ANN001
        if not self.vertical:
            yield from super().__rich_console__(console, options)
            return
        size = options.height or console.height
        has_thumb = bool(
            self.window_size and size and self.virtual_size and size != self.virtual_size
        )
        top = n = 0
        if has_thumb:
            n = min(size, max(3, round(size * self.window_size / self.virtual_size)))
            span = self.virtual_size - self.window_size
            ratio = self.position / span if span > 0 else 0
            top = round((size - n) * min(1, max(0, ratio)))
        for r in range(size):
            in_thumb = has_thumb and top <= r < top + n
            if in_thumb:
                meta = {"@mouse.down": "grab"}
            elif has_thumb:
                meta = {"@mouse.down": "scroll_up" if r < top else "scroll_down"}
            else:
                meta = {}
            for c in range(WIDTH):
                glyph, fg, bg = thumb_cell(r - top, n, c) if in_thumb else (" ", None, TRACK)
                yield Segment(
                    glyph,
                    Style(color=_color(fg) if fg else None, bgcolor=_color(bg), meta=meta),
                )
            yield Segment.line()


def install() -> None:
    """Make the green 3D scrollbar the one every widget uses."""
    ScrollBar.renderer = GreenScrollBarRender
