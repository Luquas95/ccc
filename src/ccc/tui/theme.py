"""ccc's look: one colour theme — Textual's dark one — plus ccc's own
colours, used by every view and window as $ccc-… variables. The apps
hand them to Textual (App.get_theme_variable_defaults), so they reach
every stylesheet already when it's parsed.

The colours sit on the xterm 256-colour cube, like the buttons
(layout.BUTTON_CSS): in a 256-colour terminal (tmux) Textual rounds to
the nearest one, and two near colours would become one."""
from __future__ import annotations

NAME = "textual-dark"

VARIABLES = {
    "ccc-background": "#000000",  # the page behind the panels
    "ccc-sidebar": "#000000",  # the menu on the left
    "ccc-line": "#3a3a3a",  # dividing lines, panel frames
    "ccc-title": "#5fafd7",  # panel and window titles
    "ccc-selection": "#005f87",  # the selected row / view
    "ccc-human": "#5f87af",  # your messages
    "ccc-claude": "#5faf5f",  # Claude's replies
    "ccc-frame": "#3a3a3a",  # frame lines when ccc has no tmux frame (see frame_variables)
}

# The frame lines (the tmux borders and ccc's own panel lines) have the
# colour of where the keys go: Claude Code's or ccc's. The same two colours
# in tmux (colour N of the 256 cube, as Textual's hex is rounded to) and in
# ccc, so a line looks the same on both sides of the border.
FRAME_CLAUDE, TMUX_FRAME_CLAUDE = "#5faf5f", "colour71"
FRAME_CCC, TMUX_FRAME_CCC = "#5fafd7", "colour74"


def frame_variables(keys_in: str | None) -> dict[str, str]:
    """VARIABLES with ccc-frame for `keys_in`: "claude", "ccc", or None
    (no tmux frame to match: the plain line colour)."""
    frame = {"claude": FRAME_CLAUDE, "ccc": FRAME_CCC}.get(keys_in or "")
    return {**VARIABLES, "ccc-frame": frame} if frame else VARIABLES
