"""The Archive view: archived conversations, read only. x restores one
(back to Conversations, its interactive Claude Code started again by the
daemon), Enter restores it and opens it there, Delete deletes it (asks
first)."""
from __future__ import annotations

from textual.widgets import DataTable

from ccc.i18n import _
from ccc.models import Queue
from ccc.tui.conversations import ConversationsScreen
from ccc.tui.layout import NEW_CONVERSATION_BUTTON

# Conversation actions that make no sense for an archived one.
DISABLED_ACTIONS = {"tasks", "approve", "retry_queue", "prompt_preset"}


class ArchiveScreen(ConversationsScreen):
    VIEW = "archive"
    SUB_TITLE = _("Archive")
    ARCHIVED = True
    BANNER_TEXT = _("EMPTY")

    BINDINGS = [
        ("x", "toggle_archive", _("Restore")),
        # Safe here: no Claude Code runs next to the Archive (Ctrl+D is
        # Claude's exit, #31).
        ("delete", "delete_conversation", _("Delete")),
    ]

    DEFAULT_CSS = """
    ArchiveScreen #main > #message-input, ArchiveScreen #main > #prompt-presets-bar {
        display: none;
    }
    """

    def __init__(self, storage, select_queue_id: int | None = None):
        super().__init__(storage, select_queue_id=select_queue_id)
        self._focus_input_on_mount = False  # no message box here

    def sidebar_buttons(self):
        return [NEW_CONVERSATION_BUTTON]

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in DISABLED_ACTIONS:
            return False
        return super().check_action(action, parameters)

    def _shows_nothing(self, queue: Queue | None) -> bool:
        # An archived conversation's transcript is shown (read only).
        return queue is None

    async def _open_and_focus(self, queue_id: int) -> None:
        await self._show_queue(queue_id)
        self.query_one("#conversation-queue-list", DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "conversation-queue-list":
            self.action_restore_and_open()

    def action_restore_and_open(self) -> None:
        queue_id = self._current_queue_id
        if queue_id is None:
            return
        self.storage.set_queue_archived(queue_id, False)
        self.open_conversation(queue_id)  # now Conversations' to show
