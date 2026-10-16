import pytest

from ccc import cli_input, managed_sessions
from ccc.live_delivery import DeliveryResult
from ccc.models import DeliveryMode
from ccc.prompt_presets import PromptPreset, save_prompt_presets
from ccc.storage import Storage


@pytest.fixture
def setup(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "h.db")
    save_prompt_presets(storage, [PromptPreset("Go", "Pokračuj.", True), PromptPreset("File", "Soubor: ", False)])
    cli = storage.create_queue("cli", str(tmp_path), "s1", delivery_mode=DeliveryMode.INTERACTIVE)
    headless = storage.create_queue("h", str(tmp_path), "s2")
    typed = []
    monkeypatch.setattr(managed_sessions, "is_running", lambda qid: True)
    monkeypatch.setattr(managed_sessions, "paste_and_submit",
                        lambda qid, text, submit=True: typed.append((qid, text, submit)) or DeliveryResult(True))
    return storage, cli, headless, typed


def test_send_preset_is_typed_and_submitted(setup):
    storage, cli, _, typed = setup
    assert cli_input.apply_preset(storage, cli.id, 1) is None
    assert typed == [(cli.id, "Pokračuj.", True)]


def test_insert_preset_stays_in_the_input_line(setup):
    storage, cli, _, typed = setup
    assert cli_input.apply_preset(storage, cli.id, 2) is None
    assert typed == [(cli.id, "Soubor: ", False)]


def test_errors(setup, monkeypatch):
    storage, cli, headless, typed = setup
    assert "No preset on Alt+5" in cli_input.apply_preset(storage, cli.id, 5)
    assert "Not an interactive" in cli_input.apply_preset(storage, headless.id, 1)
    monkeypatch.setattr(managed_sessions, "is_running", lambda qid: False)
    assert "isn't running" in cli_input.apply_preset(storage, cli.id, 1)
    assert typed == []


def test_paste_without_submit_sends_no_enter(monkeypatch):
    calls = []
    monkeypatch.setattr(managed_sessions, "_tmux", lambda *args, input_text=None: calls.append(args) or
                        __import__("subprocess").CompletedProcess(args, 0, "", ""))
    managed_sessions.paste_and_submit(3, "x", submit=False)
    assert [c[0] for c in calls] == ["load-buffer", "paste-buffer"]
