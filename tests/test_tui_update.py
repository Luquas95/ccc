import pytest
from textual.widgets import Button, Static

from ccc import updates
from ccc.tui.app import CCContinueApp
from ccc.tui.update import UpdateModal

STATE = updates.UpdateState(checked_at="2026-10-30T12:00:00", behind=2, remote_head="abc1234", android=True,
                            commits=["abc1234 Add rate limiting", "def5678 Fix the login"])


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(updates, "refusal", lambda storage, *a: None)


def _app(tmp_path):
    return CCContinueApp(str(tmp_path / "history.db"))


@pytest.mark.asyncio
async def test_a_new_version_shows_a_line_and_the_key_opens_the_window(tmp_path):
    app = _app(tmp_path)
    updates.save(app.storage, STATE)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        line = app.screen.query_one("#update-state", Static)
        assert line.display and "2 new" in line.render().plain
        await pilot.press("U")
        await pilot.pause()
        assert isinstance(app.screen, UpdateModal)
        info = app.screen.query_one("#update-info", Static).render().plain
        assert "Add rate limiting" in info and "Fix the login" in info and "Android app changed" in info
        assert not app.screen.query_one("#update-apply", Button).disabled


@pytest.mark.asyncio
async def test_no_line_when_up_to_date_or_looking_is_off(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        assert not app.screen.query_one("#update-state", Static).display
        updates.save(app.storage, STATE)
        app.storage.set_setting(updates.CHECK_KEY, "off")
        app.screen.refresh_daemon_state()
        assert not app.screen.query_one("#update-state", Static).display


@pytest.mark.asyncio
async def test_the_window_says_why_it_cant_update_and_applies_when_it_can(tmp_path, monkeypatch):
    app = _app(tmp_path)
    updates.save(app.storage, STATE)
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        monkeypatch.setattr(updates, "refusal", lambda storage, *a: "A task is running (shop) — the restart would stop it.")
        await pilot.press("U")
        await pilot.pause()
        assert "shop" in app.screen.query_one("#update-info", Static).render().plain
        assert app.screen.query_one("#update-apply", Button).disabled
        await pilot.press("escape")
        await pilot.pause()
        monkeypatch.setattr(updates, "refusal", lambda storage, *a: None)
        applied = []
        monkeypatch.setattr(updates, "apply", lambda storage: applied.append(1) or (True, "Updated to abc1234 — ccc is restarting."))
        await pilot.press("U")
        await pilot.pause()
        app.screen.query_one("#update-apply", Button).press()
        await pilot.pause(0.3)
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert applied == [1]
        assert "restarting" in app.screen.query_one("#update-info", Static).render().plain


@pytest.mark.asyncio
async def test_check_again_looks_now(tmp_path, monkeypatch):
    app = _app(tmp_path)
    updates.save(app.storage, STATE)
    looked = []
    monkeypatch.setattr(updates, "check", lambda storage: looked.append(1) or updates.save(storage, updates.UpdateState(
        checked_at="2026-10-30T13:00:00")))
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("U")
        await pilot.pause()
        app.screen.query_one("#update-check", Button).press()
        await pilot.pause(0.3)
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert looked == [1]
        assert "up to date" in app.screen.query_one("#update-info", Static).render().plain
