from unittest.mock import patch

import pytest

from ccc.session_discovery import DiscoveredSession
from ccc.storage import Storage
from ccc.tui.session_picker import SessionPickerScreen
from textual.app import App
from textual.widgets import DataTable


FAKE_SESSIONS = [
    DiscoveredSession(session_id="sess-a", name="dev-46", cwd="/home/lukas/DEV", kind="interactive", status="idle"),
    DiscoveredSession(session_id="sess-b", name="dev-75", cwd="/home/lukas/DEV", kind="interactive", status="busy"),
]


@pytest.mark.asyncio
async def test_session_picker_lists_discovered_sessions(tmp_path):
    storage = Storage(tmp_path / "history.db")
    screen = SessionPickerScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    with patch("ccc.tui.session_picker.discover_sessions", return_value=FAKE_SESSIONS):
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.screen.query_one("#session-picker-table", DataTable)
            rows = [str(cell) for row_key in table.rows for cell in table.get_row(row_key)]
            assert any("dev-46" in cell for cell in rows)
            assert any("dev-75" in cell for cell in rows)
            assert any("busy" in cell for cell in rows)


@pytest.mark.asyncio
async def test_selecting_a_session_and_sending_a_prompt_attaches_it(tmp_path):
    storage = Storage(tmp_path / "history.db")
    screen = SessionPickerScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    with patch("ccc.tui.session_picker.discover_sessions", return_value=FAKE_SESSIONS):
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.screen.query_one("#session-picker-table", DataTable)
            table.move_cursor(row=1)  # dev-75
            await pilot.press("enter")
            await pilot.pause()

            text_area = app.screen.query_one("#attach-prompt-text")
            text_area.text = "ahoj dev-75"
            await pilot.click("#attach-prompt-submit")
            await pilot.pause()

            queue = storage.get_queue_by_session_id("sess-b")
            assert queue is not None
            assert queue.always_resume is True
            assert queue.project_path == "/home/lukas/DEV"
            item = storage.next_pending_item(queue.id)
            assert item.prompt_text == "ahoj dev-75"
