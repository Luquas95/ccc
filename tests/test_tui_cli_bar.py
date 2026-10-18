import pytest
from textual.widgets import Static

from ccc.prompt_presets import PromptPreset, save_prompt_presets
from ccc.storage import Storage
from ccc.tui import cli_bar


@pytest.fixture
def storage(tmp_path):
    storage = Storage(tmp_path / "h.db")
    save_prompt_presets(storage, [PromptPreset("Go on", "Pokračuj.", True), PromptPreset("File", "Soubor: ", False)])
    return storage


@pytest.mark.asyncio
async def test_bar_shows_presets_and_keys(storage):
    app = cli_bar.CliBar(storage.db_path)
    async with app.run_test(size=(120, 2)) as pilot:
        await pilot.pause()
        items = [str(w.render()) for w in app.query(".bar-preset")]
        assert len(items) == 2 and "Alt+1" in items[0] and "Go on" in items[0]
        # Only presets: the keys are in ccc's key strip at the bottom.
        assert not app.query("#bar-keys")


@pytest.mark.asyncio
async def test_click_types_the_preset_into_claude_and_goes_back(storage, monkeypatch):
    applied, tmux = [], []
    monkeypatch.setattr(cli_bar.cli_pane, "find", lambda: ("%5", 7))
    monkeypatch.setattr(cli_bar, "apply_preset", lambda s, q, n: applied.append((q, n)) or None)
    monkeypatch.setattr(cli_bar.subprocess, "run", lambda args, capture_output: tmux.append(args))
    app = cli_bar.CliBar(storage.db_path)
    async with app.run_test(size=(120, 2)) as pilot:
        await pilot.pause()
        await pilot.click("#bar-preset-2")
        await pilot.pause()
    assert applied == [(7, 2)]
    assert ["tmux", "select-pane", "-t", "%5"] in tmux


@pytest.mark.asyncio
async def test_bar_follows_preset_changes(storage, monkeypatch):
    app = cli_bar.CliBar(storage.db_path)
    async with app.run_test(size=(120, 2)) as pilot:
        await pilot.pause()
        save_prompt_presets(storage, [PromptPreset("Only", "x", True)])
        await app.refresh_presets()
        await pilot.pause()
        assert len(app.query(".bar-preset")) == 1
