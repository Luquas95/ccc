from ccc.prompt_presets import KEY, MAX_PRESETS, PromptPreset, load_prompt_presets, save_prompt_presets
from ccc.storage import Storage


def test_round_trip_keeps_order_and_mode(tmp_path):
    s = Storage(tmp_path / "h.db")
    presets = [PromptPreset("Pokračuj", "Pokračuj.", True), PromptPreset("Soubor", "Zkontroluj:\n", False)]
    save_prompt_presets(s, presets)
    assert load_prompt_presets(s) == presets


def test_nothing_saved_is_empty(tmp_path):
    assert load_prompt_presets(Storage(tmp_path / "h.db")) == []


def test_broken_json_and_bad_items_are_skipped(tmp_path):
    s = Storage(tmp_path / "h.db")
    s.set_setting(KEY, "{nope")
    assert load_prompt_presets(s) == []
    s.set_setting(KEY, '[{"name": "", "text": "x"}, {"name": "ok", "text": "go", "send_now": true}, 3]')
    assert load_prompt_presets(s) == [PromptPreset("ok", "go", True)]


def test_at_most_nine(tmp_path):
    s = Storage(tmp_path / "h.db")
    save_prompt_presets(s, [PromptPreset(f"p{i}", "t", False) for i in range(12)])
    assert len(load_prompt_presets(s)) == MAX_PRESETS
