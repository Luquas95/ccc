"""Task queue editor for one conversation: the pending prompts it will
work through one after another, plus its pause / auto-continue switches."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rich.text import Text
from textual.binding import Binding
from textual.containers import Container
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Static, TextArea

from ccc.limits import RESET_BUFFER
from ccc.schedule import format_when, parse_when
from ccc.storage import Storage
from ccc.usage_api import get_pro_usage
from ccc.tui.layout import MODAL_CSS

PREVIEW_CHARS = 100


@dataclass
class TaskEdit:
    text: str
    not_before: datetime | None


def _next_five_hour_reset() -> datetime | None:
    usage = get_pro_usage()
    if usage is None or usage.five_hour is None:
        return None
    return usage.five_hour.resets_at.astimezone().replace(tzinfo=None) + RESET_BUFFER


class TaskEditModal(ModalScreen):
    """Multi-line editor for one task plus when it may start. Dismisses
    with a TaskEdit, or None when cancelled (or left empty)."""

    DEFAULT_CSS = MODAL_CSS.format(cls="TaskEditModal") + """
    TaskEditModal TextArea {
        height: 14;
    }
    TaskEditModal .modal-hint {
        color: $text-muted;
    }
    TaskEditModal #task-when {
        margin-bottom: 0;
    }
    TaskEditModal #task-error {
        color: red;
    }
    """

    BINDINGS = [
        # priority: TextArea would otherwise swallow these keys.
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, text: str = "", title: str = "New task", not_before: datetime | None = None):
        super().__init__()
        self.initial_text = text
        self.box_title = title
        self.initial_when = not_before.strftime("%Y-%m-%d %H:%M") if not_before else ""

    def compose(self):
        box = Container(
            TextArea(self.initial_text, id="task-text"),
            Static("Run at (empty = as soon as possible; HH:MM · YYYY-MM-DD HH:MM · reset)", classes="modal-label"),
            Input(self.initial_when, placeholder="as soon as possible", id="task-when"),
            Static("", id="task-error"),
            Static("Ctrl+S save  ·  Esc cancel", classes="modal-hint"),
        )
        box.border_title = self.box_title
        yield box

    def on_mount(self) -> None:
        self.query_one("#task-text", TextArea).focus()

    def action_save(self) -> None:
        text = self.query_one("#task-text", TextArea).text.strip()
        if not text:
            self.dismiss(None)
            return
        when_text = self.query_one("#task-when", Input).value
        reset_at = _next_five_hour_reset() if when_text.strip().lower() == "reset" else None
        try:
            not_before = parse_when(when_text, datetime.now(), reset_at=reset_at)
        except ValueError as exc:
            self.query_one("#task-error", Static).update(Text(str(exc)))
            return
        self.dismiss(TaskEdit(text, not_before))

    def action_cancel(self) -> None:
        self.dismiss(None)


class TasksModal(ModalScreen):
    DEFAULT_CSS = MODAL_CSS.format(cls="TasksModal") + """
    TasksModal > Container {
        width: 90%;
        max-width: 130;
        height: 80%;
    }
    TasksModal #tasks-state {
        margin-bottom: 1;
    }
    TasksModal #tasks-table {
        height: 1fr;
    }
    TasksModal #tasks-table > .datatable--cursor {
        background: blue;
        color: white;
        text-style: bold;
    }
    TasksModal .modal-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("a", "add", "Add"),
        ("e", "edit", "Edit"),
        ("delete", "delete", "Delete"),
        ("ctrl+up", "move(-1)", "Move up"),
        ("ctrl+down", "move(1)", "Move down"),
        ("p", "toggle_pause", "Pause/resume"),
        ("o", "toggle_auto", "Auto-continue"),
        ("escape", "close", "Close"),
    ]

    def __init__(self, storage: Storage, queue_id: int):
        super().__init__()
        self.storage = storage
        self.queue_id = queue_id
        self._item_ids: list[int] = []

    def compose(self):
        queue = self.storage.get_queue(self.queue_id)
        box = Container(
            Static(id="tasks-state"),
            DataTable(id="tasks-table"),
            Static(
                "a add  ·  e/Enter edit  ·  Del delete  ·  Ctrl+↑/↓ move  ·  p pause/resume  ·  "
                "o auto-continue  ·  Esc close",
                classes="modal-hint",
            ),
        )
        box.border_title = f"Tasks — {queue.name}"
        yield box

    def on_mount(self) -> None:
        table = self.query_one("#tasks-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "When", "Task")
        self._refresh()
        table.focus()

    def _refresh(self, select_item_id: int | None = None) -> None:
        queue = self.storage.get_queue(self.queue_id)
        auto = "on" if queue.auto_continue else "off"
        state = "paused" if queue.paused else "running"
        self.query_one("#tasks-state", Static).update(
            Content.assemble(
                ("Auto-continue: ", "bold"), (auto, "green" if queue.auto_continue else "yellow"), " (o)   ·   ",
                ("Queue: ", "bold"), (state, "yellow" if queue.paused else "green"), " (p)",
            )
        )
        table = self.query_one("#tasks-table", DataTable)
        previous_row = table.cursor_row
        table.clear()
        items = self.storage.list_pending_items(self.queue_id)
        self._item_ids = [i.id for i in items]
        for n, item in enumerate(items, start=1):
            lines = item.prompt_text.strip().splitlines() or [""]
            preview = lines[0][:PREVIEW_CHARS] + (" …" if len(lines) > 1 or len(lines[0]) > PREVIEW_CHARS else "")
            table.add_row(str(n), format_when(item.not_before, datetime.now()) or "—", Text(preview))
        if not items:
            return
        if select_item_id in self._item_ids:
            table.move_cursor(row=self._item_ids.index(select_item_id))
        elif previous_row is not None:
            table.move_cursor(row=min(previous_row, len(items) - 1))

    def _selected_item_id(self) -> int | None:
        row = self.query_one("#tasks-table", DataTable).cursor_row
        if row is None or row >= len(self._item_ids):
            return None
        return self._item_ids[row]

    def action_add(self) -> None:
        def added(edit: TaskEdit | None) -> None:
            if edit:
                item = self.storage.add_queue_item(self.queue_id, edit.text, not_before=edit.not_before)
                self._refresh(select_item_id=item.id)

        self.app.push_screen(TaskEditModal(), added)

    def action_edit(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        current = next(i for i in self.storage.list_pending_items(self.queue_id) if i.id == item_id)

        def edited(edit: TaskEdit | None) -> None:
            if edit:
                self.storage.update_item_text(item_id, edit.text)
                self.storage.update_item_schedule(item_id, edit.not_before)
                self._refresh(select_item_id=item_id)

        self.app.push_screen(
            TaskEditModal(current.prompt_text, title="Edit task", not_before=current.not_before), edited
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_edit()

    def action_delete(self) -> None:
        item_id = self._selected_item_id()
        if item_id is not None:
            self.storage.skip_item(item_id)
            self._refresh()

    def action_move(self, delta: int) -> None:
        item_id = self._selected_item_id()
        if item_id is not None and self.storage.move_item(item_id, delta):
            self._refresh(select_item_id=item_id)

    def action_toggle_pause(self) -> None:
        queue = self.storage.get_queue(self.queue_id)
        self.storage.set_queue_paused(self.queue_id, not queue.paused)
        self._refresh()

    def action_toggle_auto(self) -> None:
        queue = self.storage.get_queue(self.queue_id)
        self.storage.set_queue_auto_continue(self.queue_id, not queue.auto_continue)
        self._refresh()

    def action_close(self) -> None:
        self.dismiss(None)
