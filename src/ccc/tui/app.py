from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from textual.app import App

from ccc import keymap
from ccc.export_paths import SCREENSHOTS, export_dir
from ccc.i18n import _
from ccc.storage import Storage
from ccc.tui.dashboard import DashboardScreen
from ccc.tui.exports import send_export


class CCContinueApp(App):
    TITLE = "ccc"

    """A pure viewer/editor of the queue database. It never executes
    prompts itself — only `ccc-daemon` does that. This app can be
    opened and closed freely (e.g. inside a tmux window over SSH) without
    affecting whether queued prompts keep running."""

    # No command palette (and with it no Maximize / Minimize): what it
    # offered — quit, screenshot, theme — lives in the footer and Settings.
    ENABLE_COMMAND_PALETTE = False
    ESCAPE_TO_MINIMIZE = False

    BINDINGS = [
        keymap.binding("app.settings", "settings", _("Settings"), priority=True),
        # Not Ctrl+T, Claude Code's to-do list key (#31); Alt+S is free there.
        keymap.binding("app.screenshot", "take_screenshot", _("Screenshot"), show=False, priority=True),
        keymap.binding("app.quit", "quit", _("Close"), priority=True),
    ]

    def __init__(self, db_path: str):
        super().__init__()
        self.storage = Storage(db_path)

    async def on_mount(self) -> None:
        from ccc.tui.settings import saved_theme

        theme = saved_theme(self.storage, self.available_themes)
        if theme:
            self.theme = theme
        # The user's shortcuts (Settings → Keyboard shortcuts).
        self.set_keymap(keymap.load(self.storage))
        from ccc.tui import cli_pane

        # Same frame in every view (see cli_pane.style_window); there the
        # key list is the strip under the window (footer_strip).
        cli_pane.style_window(keymap.current(self.storage))
        if cli_pane.available():
            # A Claude Code pane left by the previous ccc process (killed,
            # restarted): no screen of this one owns it, so none would close
            # it and every view would sit in the sidebar column next to it.
            # Conversations opens its own again.
            cli_pane.close()
        self.footer_strip = cli_pane.available() and cli_pane.find_strip() is not None
        if self.footer_strip:
            self.set_interval(0.3, self.publish_footer)
        for screen in self.initial_screens():
            await self.push_screen(screen)

    footer_strip = False
    _published_footer: str | None = None
    # True while the shortcuts window waits for a key: no binding fires,
    # every key goes to that window (tui.keys).
    capturing_key = False

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        return False if self.capturing_key else True

    def get_key_display(self, binding) -> str:
        # Ctrl keys as Textual shows them (^p); others the way ccc names
        # them everywhere (Alt+S, Ctrl+], +).
        if binding.key_display:
            return binding.key_display
        if binding.key.startswith("ctrl+") and len(binding.key) == 6:
            return super().get_key_display(binding)
        return keymap.pretty(binding.key)

    def apply_keymap(self) -> None:
        """The saved shortcuts changed: use them everywhere — bindings,
        the menu's and buttons' keys, ccc's tmux keys."""
        from ccc.tui import cli_pane
        from ccc.tui.layout import SidebarScreen

        self.set_keymap(keymap.load(self.storage))
        for screen in self.screen_stack:
            if isinstance(screen, SidebarScreen):
                screen.refresh_key_labels()
        cli_pane.apply_keys(keymap.current(self.storage), self.storage.db_path)

    def publish_footer(self) -> None:
        """Hand the current screen's keys to the strip under the window."""
        import subprocess

        from ccc.tui.footer_strip import FOOTER_OPTION, encode, footer_items

        value = encode(footer_items(self))
        if value != self._published_footer:
            self._published_footer = value
            subprocess.run(["tmux", "set-option", "-w", "-t", os.environ["TMUX_PANE"], FOOTER_OPTION, value],
                           capture_output=True)

    def initial_screens(self) -> list:
        return [DashboardScreen(self.storage)]

    async def action_quit(self) -> None:
        """Close ccc for you. In ccc's own tmux (the always-on instance)
        that means detaching your terminal — quitting would only restart
        the TUI a second later, and other devices stay attached; on ccc's
        server Ctrl+Q is a tmux key doing just that (cli_pane), this is
        the fallback (e.g. q on the Dashboard). Elsewhere: quit."""
        from ccc import instance

        if instance.inside_ccc_tmux():
            import subprocess

            subprocess.run(["tmux", "detach-client"], capture_output=True)
            return
        self.exit()

    def action_settings(self) -> None:
        from ccc.tui.settings import SettingsModal

        if not isinstance(self.screen, SettingsModal):
            self.push_screen(SettingsModal(self.storage))

    def action_take_screenshot(self) -> None:
        folder = export_dir(self.storage, SCREENSHOTS)
        path = self.save_screenshot(f"ccc-{datetime.now():%Y-%m-%d_%H-%M-%S}.svg", str(folder))
        self.notify(path, title=_("Screenshot saved"))
        send_export(self, self.storage, Path(path))


def run_app(db_path: str) -> None:
    app = CCContinueApp(db_path)
    app.run()
