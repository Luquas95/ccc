"""Preset prompts (Alt+1 … Alt+9) for an interactive conversation: typed
straight into its Claude Code — "⏎ send" pastes and presses Enter, "✎
insert" leaves the text in Claude's input line. Used by ccc's own Alt+N
and by the tmux key bindings of the Claude Code pane (`ccc preset N`)."""
from __future__ import annotations

from ccc import managed_sessions
from ccc.i18n import _
from ccc.prompt_presets import load_prompt_presets


def apply_preset(storage, queue_id: int, number: int) -> str | None:
    """Type preset `number` into the conversation's Claude Code. Returns
    an error message to show, or None when done."""
    presets = load_prompt_presets(storage)
    if not 1 <= number <= len(presets):
        return _("No preset on Alt+{n} — add one in Settings (Ctrl+P).").format(n=number)
    queue = storage.find_queue(queue_id)
    if queue is None or not queue.delivery_mode.managed:
        return _("Not an interactive conversation.")
    if not managed_sessions.is_running(queue_id):
        return _("Claude Code isn't running for this conversation yet.")
    preset = presets[number - 1]
    result = managed_sessions.paste_and_submit(queue_id, preset.text, submit=preset.send_now)
    return None if result.delivered else (result.error or _("Couldn't type it into Claude Code."))
