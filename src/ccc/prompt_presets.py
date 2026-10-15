"""Preset prompts: texts used often, inserted into (or sent to) the open
conversation with Alt+1 … Alt+9. Edited in Settings, stored as JSON in
settings."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

KEY = "prompt_presets"
MAX_PRESETS = 9


@dataclass(frozen=True)
class PromptPreset:
    name: str
    text: str
    send_now: bool = False  # True: sent right away; False: only put into the message box


def load_prompt_presets(storage) -> list[PromptPreset]:
    try:
        data = json.loads(storage.get_setting(KEY) or "[]")
    except ValueError:
        return []
    presets = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("text"), str):
            if item["name"].strip() and item["text"].strip():
                presets.append(PromptPreset(item["name"], item["text"], bool(item.get("send_now", False))))
    return presets[:MAX_PRESETS]


def save_prompt_presets(storage, presets: list[PromptPreset]) -> None:
    storage.set_setting(KEY, json.dumps([asdict(p) for p in presets[:MAX_PRESETS]], ensure_ascii=False))
