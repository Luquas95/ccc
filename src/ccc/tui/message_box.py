"""Multi-line message box under a conversation's transcript: Enter sends,
Ctrl+J (works in every terminal) or Shift+Enter (where the terminal
reports it) starts a new line."""
from __future__ import annotations

from dataclasses import dataclass

from textual import events
from textual.message import Message
from textual.widgets import TextArea

NEWLINE_KEYS = ("ctrl+j", "shift+enter")


class MessageBox(TextArea):
    DEFAULT_CSS = """
    MessageBox {
        height: auto;
        min-height: 3;
        max-height: 10;
    }
    """

    @dataclass
    class Submitted(Message):
        box: "MessageBox"
        text: str

    def __init__(self, placeholder: str = "", **kwargs):
        super().__init__(soft_wrap=True, show_line_numbers=False, tab_behavior="focus", **kwargs)
        self.placeholder = placeholder

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.post_message(self.Submitted(self, self.text))
            return
        if event.key in NEWLINE_KEYS:
            event.stop()
            event.prevent_default()
            start, end = self.selection
            self._replace_via_keyboard("\n", start, end)
            return
        await super()._on_key(event)
