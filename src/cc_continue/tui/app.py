from __future__ import annotations

from textual.app import App

from cc_continue.orchestrator import Orchestrator, RunFn
from cc_continue.runner import execute
from cc_continue.storage import Storage
from cc_continue.tui.dashboard import DashboardScreen


class CCContinueApp(App):
    def __init__(self, db_path: str, run_fn: RunFn = execute):
        super().__init__()
        self.storage = Storage(db_path)
        self.orchestrator = Orchestrator(self.storage, run_fn=run_fn)

    async def on_mount(self) -> None:
        await self.orchestrator.start_all()
        await self.push_screen(DashboardScreen(self.storage))

    async def on_unmount(self) -> None:
        await self.orchestrator.stop_all()


def run_app(db_path: str) -> None:
    app = CCContinueApp(db_path)
    app.run()
