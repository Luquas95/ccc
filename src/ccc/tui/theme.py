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
    "ccc-frame": "#5faf5f",  # frame lines (the same green as the tmux frame, FRAME)
}

# The frame lines — the tmux borders and ccc's own panel lines — are one
# colour: green. colourN is the 256-cube colour Textual's hex is rounded
# to, so a line looks the same on both sides of a border.
FRAME, TMUX_FRAME = "#5faf5f", "colour71"
