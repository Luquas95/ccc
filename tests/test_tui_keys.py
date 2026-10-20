import json

import pytest
from textual.widgets import DataTable, Input, Static

from ccc import keymap
from ccc.storage import Storage
from ccc.tui.analytics import AnalyticsScreen
from ccc.tui.app import CCContinueApp
from ccc.tui.dashboard import DashboardScreen
from ccc.tui.keys import KeysModal
from ccc.tui.settings import SettingsModal


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")


def _app(tmp_path):
    db_path = tmp_path / "history.db"
    Storage(db_path)
    return CCContinueApp(str(db_path))


async def _open_keys(app, pilot):
    await pilot.press("ctrl+p")
    await pilot.pause()
    assert isinstance(app.screen, SettingsModal)
    app.screen._edit_keys()
    await pilot.pause()
    assert isinstance(app.screen, KeysModal)
    return app.screen


def _select(modal, action_id):
    table = modal.query_one("#keys-table", DataTable)
    table.move_cursor(row=table.get_row_index(action_id))


def _status(modal):
    return str(modal.query_one("#keys-status", Static).render())


@pytest.mark.asyncio
async def test_a_typed_key_is_saved_and_works_right_away(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        modal = await _open_keys(app, pilot)
        _select(modal, "views.analytics")
        modal.query_one("#keys-input", Input).value = "F5"
        await pilot.click("#keys-set")
        await pilot.pause()
        assert "free" in _status(modal)
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert keymap.load(app.storage) == {"views.analytics": "f5"}
        await pilot.press("escape")  # Settings
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)
        assert "F5" in str(app.screen.query_one("#nav-analytics", Static).render())
        await pilot.press("a")  # no longer Analytics
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)
        await pilot.press("f5")
        await pilot.pause()
        assert isinstance(app.screen, AnalyticsScreen)


@pytest.mark.asyncio
async def test_a_colliding_key_is_refused_with_the_reason(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        modal = await _open_keys(app, pilot)
        _select(modal, "views.analytics")
        modal.query_one("#keys-input", Input).value = "d"
        await pilot.click("#keys-set")
        await pilot.pause()
        assert "already “Dashboard”" in _status(modal)
        assert modal.keys["views.analytics"] == "a"


@pytest.mark.asyncio
async def test_pressed_key_is_captured_even_ccc_keys(tmp_path):
    # While it waits for a key, Ctrl+P / Esc don't act — they're the answer.
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        modal = await _open_keys(app, pilot)
        _select(modal, "app.screenshot")
        await pilot.click("#keys-capture")
        await pilot.pause()
        await pilot.press("ctrl+p")  # Settings' key: refused, but not opened
        await pilot.pause()
        assert app.screen is modal
        assert "already “Settings”" in _status(modal)
        await pilot.click("#keys-capture")
        await pilot.press("f6")
        await pilot.pause()
        assert modal.keys["app.screenshot"] == "f6"
        assert not app.capturing_key


@pytest.mark.asyncio
async def test_export_and_import_in_the_window(tmp_path):
    app = _app(tmp_path)
    folder = tmp_path / "keys"
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        modal = await _open_keys(app, pilot)
        modal.keys["app.screenshot"] = "f6"
        modal.query_one("#keys-folder", Input).value = str(folder)
        await pilot.click("#keys-export")
        await pilot.pause()
        assert json.loads((folder / keymap.EXPORT_NAME).read_text())["keys"]["app.screenshot"] == "f6"

        (folder / keymap.EXPORT_NAME).write_text(json.dumps(
            {"format": "ccc-keys", "version": 1, "keys": {"views.analytics": "d"}}))
        await pilot.click("#keys-import")
        await pilot.pause()
        assert "collide" in _status(modal)
        assert modal.keys["views.analytics"] == "a"


@pytest.mark.asyncio
async def test_the_users_keys_apply_at_start(tmp_path):
    db_path = tmp_path / "history.db"
    keymap.save(Storage(db_path), {**keymap.defaults(), "views.analytics": "f5"})
    app = CCContinueApp(str(db_path))
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()
        assert isinstance(app.screen, AnalyticsScreen)
