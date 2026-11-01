"""ccc's look: one colour theme — Textual's dark one on a black ground — plus ccc's own
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
# Textual's dark theme on a black ground, so that every widget (tables,
# lists, dialogs) sits on the same colour as the page. The panel colour —
# the blue key list at the bottom — is Textual's own, set here because it
# would otherwise be derived from the (now black) surface and turn black.
THEME = dataclasses.replace(
    BUILTIN_THEMES["textual-dark"], name=NAME, background="#000000", surface="#000000", panel="#242F38")

VARIABLES = {
    "ccc-background": "#000000",  # the page behind the panels
    "ccc-sidebar": "#000000",  # the menu on the left
    "ccc-line": "#3a3a3a",  # dividing lines, panel frames
    "ccc-title": "#5fd7af",  # panel and window titles, the footer's key caps (repo-doctor's mint)
    "ccc-selection": "#005f87",  # the selected row / view
    "ccc-human": "#5f87af",  # your messages
    "ccc-claude": "#5faf5f",  # Claude's replies
    "ccc-nav": "#2563eb",  # the main menu's buttons (Dashboard … Analytics)
    "ccc-nav-hover": "#3b82f6",  # …under the pointer, and the open view's
    "ccc-nav-border": "#93c5fd",  # …their frame
    "ccc-nav-border-current": "#dbeafe",  # …the open view's frame
    "ccc-frame": "#5faf5f",  # frame lines (the same green as the tmux frame, FRAME)
}

# The frame lines — the tmux borders and ccc's own panel lines — are one
# colour: green. colourN is the 256-cube colour Textual's hex is rounded
# to, so a line looks the same on both sides of a border.
FRAME, TMUX_FRAME = "#5faf5f", "colour71"
