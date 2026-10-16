from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from ccc.export_paths import SCREENSHOTS, export_dir
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
        Binding("ctrl+p", "settings", "Settings", priority=True),
        Binding("ctrl+t", "take_screenshot", "Screenshot", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(self, db_path: str):
        super().__init__()
        self.storage = Storage(db_path)

    async def on_mount(self) -> None:
        from ccc.tui.settings import saved_theme

        theme = saved_theme(self.storage, self.available_themes)
        if theme:
            self.theme = theme
        for screen in self.initial_screens():
            await self.push_screen(screen)

    def initial_screens(self) -> list:
        return [DashboardScreen(self.storage)]

    def action_settings(self) -> None:
        from ccc.tui.settings import SettingsModal

        if not isinstance(self.screen, SettingsModal):
            self.push_screen(SettingsModal(self.storage))

    def action_take_screenshot(self) -> None:
        folder = export_dir(self.storage, SCREENSHOTS)
        path = self.save_screenshot(f"ccc-{datetime.now():%Y-%m-%d_%H-%M-%S}.svg", str(folder))
        self.notify(path, title="Screenshot saved")
        send_export(self, self.storage, Path(path))


def run_app(db_path: str) -> None:
    app = CCContinueApp(db_path)
    app.run()
