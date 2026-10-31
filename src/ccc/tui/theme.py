"""ccc's look: one colour theme — Textual's dark one on a near-black ground — plus ccc's own
colours, used by every view and window as $ccc-… variables. The apps
hand them to Textual (App.get_theme_variable_defaults), so they reach
every stylesheet already when it's parsed.

The colours sit on the xterm 256-colour cube, like the buttons
(layout.BUTTON_CSS): in a 256-colour terminal (tmux) Textual rounds to
the nearest one, and two near colours would become one."""
from __future__ import annotations

import dataclasses

from textual.theme import BUILTIN_THEMES

NAME = "ccc"
# Textual's dark theme with repo-doctor's near-black ground, so that
# every widget (tables, lists, dialogs) sits on the same colour as the page.
THEME = dataclasses.replace(
    BUILTIN_THEMES["textual-dark"], name=NAME, background="#121212", surface="#121212", panel="#1c1c1c")

VARIABLES = {
    "ccc-background": "#121212",  # the page behind the panels (repo-doctor's near-black)
    "ccc-sidebar": "#121212",  # the menu on the left
    "ccc-line": "#3a3a3a",  # dividing lines, panel frames
    "ccc-title": "#5fd7af",  # panel and window titles, the footer's key caps (repo-doctor's mint)
    "ccc-selection": "#005f87",  # the selected row / view
    "ccc-human": "#5f87af",  # your messages
    "ccc-claude": "#5faf5f",  # Claude's replies
    "ccc-frame": "#5faf5f",  # frame lines (the same green as the tmux frame, FRAME)
}

# The frame lines — the tmux borders and ccc's own panel lines — are one
# colour: green. colourN is the 256-cube colour Textual's hex is rounded
# to, so a line looks the same on both sides of a border.
FRAME, TMUX_FRAME = "#5faf5f", "colour71"

# The key list under the window: a key on a mint cap, its description dimmed.
ACCENT, MUTED, CAP_TEXT = "#5fd7af", "#8a8a8a", "#121212"
