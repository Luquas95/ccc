from pathlib import Path

import pytest
from textual.widgets import Input, Select

from ccc.notify import TELEGRAM_CHAT_KEY, TELEGRAM_TOKEN_KEY
from ccc.orchestrator import RESERVE_KEY
from ccc.presets import LaunchChoice, list_presets, save_preset
from ccc.storage import Storage
from ccc.tui.app import CCContinueApp
from ccc.tui.dashboard import DashboardScreen
from ccc.tui.settings import THEME_KEY, SettingsModal


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")


def _app(tmp_path):
    return CCContinueApp(str(tmp_path / "history.db"))


async def _open_settings(pilot, app):
    await pilot.pause()
    await pilot.press("ctrl+p")
    await pilot.pause()
    assert isinstance(app.screen, SettingsModal)
    return app.screen


def _footer_keys(app):
    return {b.binding.key for b in app.screen.active_bindings.values() if b.binding.show}


@pytest.mark.asyncio
async def test_footer_shows_only_what_the_sidebar_does_not(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        keys = _footer_keys(app)
        assert {"ctrl+p", "ctrl+q", "question_mark"} <= keys
        assert not keys & {"ctrl+t", "ctrl+d"}  # Claude Code's keys (#31)
        assert not keys & {"d", "c", "s", "v", "a", "n", "r", "q"}
        await pilot.press("c")
        await pilot.pause()
        keys = _footer_keys(app)
        assert not keys & {"d", "c", "s", "a", "n", "r", "escape"}
        assert "v" in keys  # the conversation's Review is its own action, not a view


@pytest.mark.asyncio
async def test_no_command_palette_or_maximize(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        assert app.use_command_palette is False
        # Ctrl+P now opens Settings instead of the palette.
        await _open_settings(pilot, app)


@pytest.mark.asyncio
async def test_settings_saves_everything(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        modal = await _open_settings(pilot, app)
        modal.query_one("#settings-theme", Select).value = "nord"
        await pilot.pause()
        assert app.theme == "nord"  # live preview
        modal.query_one("#settings-telegram-token", Input).value = "123:abc"
        modal.query_one("#settings-telegram-chat", Input).value = "42"
        modal.query_one("#settings-continue-text", Input).value = "Go on."
        modal.query_one("#settings-reserve", Select).value = "80"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)
        s = app.storage
        assert s.get_setting(THEME_KEY) == "nord"
        assert s.get_setting(TELEGRAM_TOKEN_KEY) == "123:abc"
        assert s.get_setting(TELEGRAM_CHAT_KEY) == "42"
        assert s.get_setting("continue_text") == "Go on."
        assert s.get_setting(RESERVE_KEY) == "80"


@pytest.mark.asyncio
async def test_empty_token_field_keeps_the_saved_token(tmp_path):
    app = _app(tmp_path)
    app.storage.set_setting(TELEGRAM_TOKEN_KEY, "secret")
    async with app.run_test(size=(140, 45)) as pilot:
        modal = await _open_settings(pilot, app)
        assert modal.query_one("#settings-telegram-token", Input).value == ""  # never shown
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.storage.get_setting(TELEGRAM_TOKEN_KEY) == "secret"


@pytest.mark.asyncio
async def test_cancel_puts_the_theme_back_and_saves_nothing(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        before = app.theme
        modal = await _open_settings(pilot, app)
        modal.query_one("#settings-theme", Select).value = "nord"
        modal.query_one("#settings-reserve", Select).value = "90"
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.theme == before
        assert app.storage.get_setting(THEME_KEY) is None
        assert app.storage.get_setting(RESERVE_KEY) is None


@pytest.mark.asyncio
async def test_saved_theme_is_applied_on_start(tmp_path):
    Storage(tmp_path / "history.db").set_setting(THEME_KEY, "nord")
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        assert app.theme == "nord"


@pytest.mark.asyncio
async def test_reserve_off_and_telegram_test_and_turn_off(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr("ccc.tui.settings.send_telegram", lambda t, c, text: sent.append((t, c)))
    app = _app(tmp_path)
    app.storage.set_setting(RESERVE_KEY, "70")
    async with app.run_test(size=(140, 45)) as pilot:
        modal = await _open_settings(pilot, app)
        assert modal.query_one("#settings-reserve", Select).value == "70"
        modal.query_one("#settings-telegram-token", Input).value = "t0k"
        modal.query_one("#settings-telegram-chat", Input).value = "7"
        modal._send_test()
        await pilot.pause(0.3)
        await app.workers.wait_for_complete()
        assert sent == [("t0k", "7")]
        modal._telegram_off()
        assert app.storage.get_setting(TELEGRAM_TOKEN_KEY) == ""
        modal.query_one("#settings-reserve", Select).value = "off"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.storage.get_setting(RESERVE_KEY) == ""


@pytest.mark.asyncio
async def test_delete_preset_and_backup(tmp_path):
    app = _app(tmp_path)
    save_preset(app.storage, "yolo", LaunchChoice(frozenset()))
    async with app.run_test(size=(140, 45)) as pilot:
        modal = await _open_settings(pilot, app)
        modal.query_one("#settings-preset", Select).value = "yolo"
        modal._delete_preset()
        assert list_presets(app.storage) == {}
        modal._backup()
        assert list((tmp_path / "backups").glob("history-*.db"))


@pytest.mark.asyncio
async def test_screenshot_saves_svg(tmp_path, monkeypatch):
    app = _app(tmp_path)
    app.storage.set_setting("export_folder", str(tmp_path / "out"))
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        app.action_take_screenshot()  # no key until #31
        await pilot.pause()
        assert len(list((tmp_path / "out" / "screenshots").glob("ccc-*.svg"))) == 1


@pytest.mark.asyncio
async def test_export_folder_saved_from_settings(tmp_path):
    from ccc.export_paths import export_folder

    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        app.screen.query_one("#settings-export-folder", Input).value = "~/my-exports"
        app.screen.query_one("#settings-export-send", Select).value = "both"
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert export_folder(app.storage) == Path.home() / "my-exports"
    assert app.storage.get_setting("export_send") == "both"


@pytest.mark.asyncio
async def test_ctrl_q_quits_outside_ccc_tmux(tmp_path):
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+q")
        await pilot.pause()
    assert app.return_code == 0


HOOK = "https://discord.com/api/webhooks/123/SECRETTOKEN"


@pytest.mark.asyncio
async def test_discord_webhook_saved_kept_and_validated(tmp_path):
    from ccc.notify import DISCORD_WEBHOOK_KEY

    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        modal = await _open_settings(pilot, app)
        modal.query_one("#settings-discord-webhook", Input).value = "https://evil.example/x"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, SettingsModal)  # refused, window stays
        assert app.storage.get_setting(DISCORD_WEBHOOK_KEY) is None
        modal.query_one("#settings-discord-webhook", Input).value = HOOK
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.storage.get_setting(DISCORD_WEBHOOK_KEY) == HOOK

        modal = await _open_settings(pilot, app)
        assert modal.query_one("#settings-discord-webhook", Input).value == ""  # never shown
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.storage.get_setting(DISCORD_WEBHOOK_KEY) == HOOK  # empty field keeps it


@pytest.mark.asyncio
async def test_discord_test_and_turn_off(tmp_path, monkeypatch):
    from ccc.notify import DISCORD_WEBHOOK_KEY

    sent = []
    monkeypatch.setattr("ccc.tui.settings.send_discord", lambda url, text: sent.append(url))
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        modal = await _open_settings(pilot, app)
        modal._send_discord_test()  # nothing filled in
        assert sent == []
        modal.query_one("#settings-discord-webhook", Input).value = HOOK
        modal._send_discord_test()
        await pilot.pause(0.3)
        await app.workers.wait_for_complete()
        assert sent == [HOOK]
        app.storage.set_setting(DISCORD_WEBHOOK_KEY, HOOK)
        modal._discord_off()
        assert app.storage.get_setting(DISCORD_WEBHOOK_KEY) == ""


@pytest.mark.asyncio
async def test_archive_folder_saved_and_archive_now(tmp_path):
    from ccc.analytics_archive import FOLDER_KEY

    app = _app(tmp_path)
    folder = tmp_path / "vault" / "ccc_analytics"
    async with app.run_test(size=(140, 45)) as pilot:
        modal = await _open_settings(pilot, app)
        modal._archive_now()  # empty field: archive is off, nothing written
        assert not (tmp_path / "analytics").exists()
        modal.query_one("#settings-archive-folder", Input).value = str(folder)
        modal._archive_now()
        assert (folder / "ccc_analytics.md").exists()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.storage.get_setting(FOLDER_KEY) == str(folder)


@pytest.mark.asyncio
async def test_ctrl_q_detaches_inside_ccc_tmux(tmp_path, monkeypatch):
    # The always-on instance: quitting would only restart the TUI.
    import subprocess

    calls = []
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/ccc,1,0")
    monkeypatch.setattr(subprocess, "run", lambda args, capture_output=True: calls.append(args))
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert calls == [["tmux", "detach-client"]]
        assert app.is_running


@pytest.mark.asyncio
async def test_another_language_restarts_the_tui(tmp_path, monkeypatch):
    from ccc import i18n

    monkeypatch.delenv("CCC_LANG", raising=False)
    for var in ("LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setattr("ccc.instance.inside_ccc_tmux", lambda: True)
    app = _app(tmp_path)
    exits = []
    monkeypatch.setattr(app, "exit", lambda *a, **k: exits.append(True))
    try:
        async with app.run_test(size=(140, 45)) as pilot:
            modal = await _open_settings(pilot, app)
            assert modal.query_one("#settings-language", Select).value == "auto"
            await pilot.press("ctrl+s")  # unchanged: no restart
            await pilot.pause()
            assert exits == [] and app.storage.get_setting(i18n.LANGUAGE_KEY) == ""
            modal = await _open_settings(pilot, app)
            modal.query_one("#settings-language", Select).value = "cs"
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert app.storage.get_setting(i18n.LANGUAGE_KEY) == "cs"
            assert exits == [True]
    finally:
        i18n.set_language("en")


@pytest.mark.asyncio
async def test_context_settings_saved_and_validated(tmp_path):
    from ccc import context_fill

    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        modal = await _open_settings(pilot, app)
        modal.query_one("#settings-context-warn", Select).value = "90"
        modal.query_one("#settings-context-danger", Select).value = "80"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, SettingsModal)  # warning above the alarm: refused
        assert app.storage.get_setting(context_fill.WARN_KEY) is None
        modal.query_one("#settings-context-warn", Select).value = "70"
        modal.query_one("#settings-context-danger", Select).value = "85"
        modal.query_one("#settings-context-window", Select).value = "1000000"
        modal.query_one("#settings-context-notify", Select).value = "off"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert not isinstance(app.screen, SettingsModal)
        assert context_fill.thresholds(app.storage) == (70, 85)
        assert context_fill.window_setting(app.storage) == 1_000_000
        assert not context_fill.notify_enabled(app.storage)


@pytest.mark.asyncio
async def test_editor_choice_offers_only_installed_editors_and_is_saved(tmp_path, monkeypatch):
    from ccc import external_editor

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("nano", "hx", "code"):
        (bin_dir / name).write_text("#!/bin/sh\n")
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    app = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        modal = await _open_settings(pilot, app)
        select = modal.query_one("#settings-editor", Select)
        assert [value for _label, value in select._options] == ["auto", "nano", "hx"]  # no display: no code
        assert select.value == "auto"
        select.value = "hx"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.storage.get_setting(external_editor.SETTING_KEY) == "hx"
        assert external_editor.command(app.storage) == ("hx",)
        modal = await _open_settings(pilot, app)
        assert modal.query_one("#settings-editor", Select).value == "hx"
