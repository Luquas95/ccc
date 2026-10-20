"""The ask window (k in Conversations / queue detail): put a question to
another conversation and read the answers — yours and the ones Claude
asked by itself (ccc.asks; the daemon passes the answers on)."""
from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Select, Static, TextArea

from ccc import asks, keymap
from ccc.i18n import N_, _
from ccc.models import Ask, AskStatus
from ccc.schedule import format_when
from ccc.tui.layout import MODAL_CSS

REFRESH_SECONDS = 2.0
STATUS_LABELS = {AskStatus.ASKED: N_("waiting for the answer"), AskStatus.ANSWERED: N_("answered"),
                 AskStatus.ERROR: N_("failed"), AskStatus.CANCELLED: N_("cancelled")}
STATUS_STYLES = {AskStatus.ASKED: "yellow", AskStatus.ANSWERED: "green", AskStatus.ERROR: "red",
                 AskStatus.CANCELLED: "dim"}


class AskModal(ModalScreen):
    DEFAULT_CSS = MODAL_CSS.format(cls="AskModal") + """
    AskModal > Container {
        width: 95%;
        max-width: 140;
        height: 95%;
    }
    AskModal TextArea {
        height: 4;
    }
    AskModal #ask-table {
        height: 7;
        margin: 1 0;
    }
    AskModal #ask-table > .datatable--cursor {
        background: blue;
        color: white;
        text-style: bold;
    }
    AskModal #ask-detail-box {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    AskModal .ask-actions {
        height: 3;
        margin-top: 1;
    }
    AskModal .ask-actions Button {
        border: none;
        height: 3;
        margin-right: 1;
        background: blue;
        color: white;
        text-style: bold;
    }
    AskModal .ask-actions Button.ask-danger {
        background: red;
    }
    AskModal .ask-actions Button:disabled {
        background: $panel;
        color: $text-muted;
    }
    AskModal .modal-hint {
        color: $text-muted;
        width: 1fr;
        padding-top: 1;
    }
    """

    BINDINGS = [
        keymap.binding("window.save", "send", _("Send"), priority=True),
        keymap.binding("window.cancel", "close", _("Close"), priority=True),
    ]

    def __init__(self, storage, queue_id: int):
        super().__init__()
        self.storage = storage
        self.queue_id = queue_id
        self._ids: list[int] = []

    def compose(self):
        queue = self.storage.get_queue(self.queue_id)
        others = [(q.name, q.id) for q in self.storage.list_queues()
                  if not q.archived and q.id != self.queue_id]
        box = Container(
            Static(_("Ask another conversation — e.g. the one working on the API, before this one changes it. The "
                     "question goes into its queue; its answer comes back here as the next message."),
                   classes="modal-hint"),
            Select(others, prompt=_("Ask which conversation?"), id="ask-target"),
            TextArea(id="ask-question"),
            Checkbox(_("Pass the answer into this conversation (Claude reads it as its next message)"), value=True,
                     id="ask-deliver"),
            DataTable(id="ask-table", cursor_type="row"),
            VerticalScroll(Static("", id="ask-detail"), id="ask-detail-box"),
            Horizontal(
                Button(_("Send"), id="ask-send"),
                Button(_("Cancel the question"), id="ask-cancel", classes="ask-danger"),
                Static(_("Ctrl+S send  ·  Esc close"), classes="modal-hint"),
                classes="ask-actions",
            ),
        )
        box.border_title = _("Questions — {name}").format(name=queue.name)
        yield box

    def on_mount(self) -> None:
        for button in self.query(".ask-actions Button"):
            button.can_focus = False
        self.query_one("#ask-question", TextArea).placeholder = _(
            "e.g. Which fields does /orders return now, and is `total` net or gross?")
        self.query_one("#ask-table", DataTable).add_columns(_("When"), "", _("Conversation"), _("State"),
                                                            _("Question"))
        self._refresh()
        self.set_interval(REFRESH_SECONDS, self._refresh)
        self.query_one("#ask-question", TextArea).focus()

    def _refresh(self) -> None:
        table = self.query_one("#ask-table", DataTable)
        previous = self.selected()
        table.clear()
        names = {q.id: q.name for q in self.storage.list_queues()}
        items = self.storage.list_asks(self.queue_id)
        self._ids = [a.id for a in items]
        now = datetime.now()
        for a in items:
            outgoing = a.from_queue_id == self.queue_id
            other = names.get(a.to_queue_id if outgoing else a.from_queue_id, "?")
            arrow = ("→" if outgoing else "←") + (" 🤖" if a.by_agent else "")
            table.add_row(format_when(a.created_at, now), arrow, other,
                          Text(_(STATUS_LABELS[a.status]), style=STATUS_STYLES[a.status]),
                          Text(a.question.splitlines()[0][:70]))
        if not items:
            table.add_row("", "", "", "", Text(_("no questions yet"), style="dim"))
        elif previous is not None and previous.id in self._ids:
            table.move_cursor(row=self._ids.index(previous.id))
        self._show_detail()

    def selected(self) -> Ask | None:
        row = self.query_one("#ask-table", DataTable).cursor_row
        if row is None or row >= len(self._ids):
            return None
        return self.storage.find_ask(self._ids[row])

    def _show_detail(self) -> None:
        a = self.selected()
        detail = self.query_one("#ask-detail", Static)
        cancel = self.query_one("#ask-cancel", Button)
        cancel.disabled = not (a is not None and a.status == AskStatus.ASKED and a.from_queue_id == self.queue_id)
        if a is None:
            detail.update(_("→ you (or Claude) asked another conversation · ← another conversation asked this one · "
                            "🤖 Claude asked by itself (the ccc tool ask_conversation)."))
            return
        parts = [Text(a.question, style="bold")]
        if a.answer:
            parts.append(Text(a.answer))
        if a.error:
            parts.append(Text(a.error, style="red"))
        if a.status == AskStatus.ASKED:
            parts.append(Text(_("The answer comes once the other conversation has handled the question."),
                              style="yellow"))
        detail.update(Text("\n\n").join(parts))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._show_detail()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        {"ask-send": self.action_send, "ask-cancel": self.action_cancel_question}.get(event.button.id, lambda: None)()

    def action_send(self) -> None:
        target = self.query_one("#ask-target", Select).value
        if target is Select.NULL:
            self.notify(_("Choose the conversation to ask."), severity="warning")
            return
        try:
            asks.ask(self.storage, self.queue_id, int(target), self.query_one("#ask-question", TextArea).text,
                     deliver=self.query_one("#ask-deliver", Checkbox).value)
        except ValueError as error:
            self.notify(str(error), severity="warning")
            return
        self.query_one("#ask-question", TextArea).text = ""
        self.notify(_("Asked — the answer comes back once the other conversation has answered."))
        self._refresh()
        self.query_one("#ask-table", DataTable).move_cursor(row=0)

    def action_cancel_question(self) -> None:
        a = self.selected()
        if a is not None and asks.cancel(self.storage, a.id):
            self.notify(_("Question cancelled."))
        self._refresh()

    def action_close(self) -> None:
        self.dismiss()
