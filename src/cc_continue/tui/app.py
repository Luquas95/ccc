from __future__ import annotations

from textual.app import App

from cc_continue.storage import Storage
from cc_continue.tui.dashboard import DashboardScreen


class CCContinueApp(App):
    """A pure viewer/editor of the queue database. It never executes
    prompts itself — only `cc-continue-daemon` does that. This app can be
    opened and closed freely (e.g. inside a tmux window over SSH) without
    affecting whether queued prompts keep running."""

    def __init__(self, db_path: str):
        super().__init__()
        self.storage = Storage(db_path)

    async def on_mount(self) -> None:
        await self.push_screen(DashboardScreen(self.storage))


def run_app(db_path: str) -> None:
    app = CCContinueApp(db_path)
    app.run()
