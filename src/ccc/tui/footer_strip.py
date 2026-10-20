"""ccc's bottom bar (its key list) as its own row across the whole window.

On ccc's tmux server ccc's window is split — ccc narrows to its menu when
Claude Code opens beside it, and its own footer wouldn't fit there. So
there the footer lives in a 1-row pane under everything, in every view,
which keeps the frame the same everywhere: ccc publishes the current
screen's keys (exactly what its footer would show) as the @ccc-footer
window option (publish), and this strip (`python -m ccc.tui.footer_strip`)
shows them; clicking one presses that key in ccc."""
from __future__ import annotations

import json
import subprocess

from rich.text import Text
from textual.app import App
from textual.containers import Horizontal
from textual.widgets import Static

from ccc import keymap

FOOTER_OPTION = "@ccc-footer"
POLL_SECONDS = 0.3

# Textual key names → tmux key names, for clicks (send-keys).
tmux_key = keymap.tmux_key


def footer_items(app) -> list[list[str]]:
    """[key shown, description, tmux key] of what the screen's footer would
    show — the same bindings Textual's Footer lists."""
    items, seen = [], set()
    for _node, binding, enabled, _tooltip in app.screen.active_bindings.values():
        if not binding.show or not enabled or binding.action in seen:
            continue
        seen.add(binding.action)
        items.append([app.get_key_display(binding), binding.description, tmux_key(binding.key) or ""])
    return items


def encode(items: list[list[str]]) -> str:
    return json.dumps(items, ensure_ascii=False)


def decode(value: str) -> list[list[str]]:
    try:
        items = json.loads(value)
    except ValueError:
        return []
    return [i for i in items if isinstance(i, list) and len(i) == 3] if isinstance(items, list) else []


def _tmux(*args: str) -> subprocess.CompletedProcess:
    # Plain `tmux`: $TMUX points at ccc's server (this runs in its pane).
    return subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=5)


class FooterStrip(App):
    CSS = """
    Screen {
        background: $footer-background;
    }
    #strip-items {
        height: 1;
    }
    .strip-item {
        width: auto;
        padding: 0 1;
    }
    .strip-item:hover {
        background: $footer-item-background;
        text-style: reverse;
    }
    """
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, main_pane: str):
        super().__init__()
        self.main_pane = main_pane
        self._shown: str | None = None

    def compose(self):
        yield Horizontal(id="strip-items")

    async def on_mount(self) -> None:
        await self.refresh_items()
        self.set_interval(POLL_SECONDS, self.refresh_items)

    async def refresh_items(self) -> None:
        value = _tmux("show-options", "-wqv", "-t", self.main_pane, FOOTER_OPTION).stdout.strip()
        if value == self._shown:
            return
        self._shown = value
        row = self.query_one("#strip-items", Horizontal)
        await row.remove_children()
        await row.mount_all(
            Static(Text.assemble((shown, "bold yellow"), " ", description),
                   classes="strip-item", name=key)
            for shown, description, key in decode(value)
        )

    def on_click(self, event) -> None:
        widget = event.widget
        if widget is None or not widget.has_class("strip-item") or not widget.name:
            return
        # Press that key in ccc, where it belongs — as if typed (-K, through
        # the client), so keys tmux binds while Claude Code is open (Alt+0)
        # do what they do when pressed.
        _tmux("select-pane", "-t", self.main_pane)
        client = _tmux("display-message", "-p", "-t", self.main_pane, "#{client_name}").stdout.strip()
        if client:
            _tmux("send-keys", "-K", "-c", client, widget.name)
        else:
            _tmux("send-keys", "-t", self.main_pane, widget.name)


def main() -> None:
    import sys

    if len(sys.argv) != 2:
        sys.exit("usage: python -m ccc.tui.footer_strip MAIN_PANE")
    FooterStrip(sys.argv[1]).run()


if __name__ == "__main__":
    main()
