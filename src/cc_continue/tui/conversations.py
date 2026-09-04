from __future__ import annotations

from rich.markup import escape
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from cc_continue.storage import Storage
from cc_continue.transcript import TranscriptEvent, find_transcript_path, parse_transcript_events


class ConversationsScreen(Screen):
    BINDINGS = [("escape", "back", "Back")]

    DEFAULT_CSS = """
    ConversationsScreen #conversation-queue-list {
        width: 32;
    }
    ConversationsScreen #conversation-transcript {
        width: 1fr;
    }
    ConversationsScreen .message-box {
        border: round cyan;
        padding: 0 1;
        margin-bottom: 1;
    }
    ConversationsScreen .message-box-human {
        border: round cyan;
    }
    ConversationsScreen .message-box-assistant {
        border: round green;
    }
    ConversationsScreen .message-header {
        color: $accent;
    }
    ConversationsScreen .tool-call-line {
        color: $text-muted;
    }
    """

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        # Per-queue cache: queue_id -> {"path": Path|None, "offset": int,
        # "events": list[TranscriptEvent]} so switching back to an
        # already-viewed queue doesn't re-parse its transcript from zero.
        self._cache: dict[int, dict] = {}
        self._current_queue_id: int | None = None

    def compose(self):
        yield Header()
        yield Horizontal(
            DataTable(id="conversation-queue-list"),
            VerticalScroll(id="conversation-transcript"),
        )
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#conversation-queue-list", DataTable)
        table.cursor_type = "row"
        table.add_column("Queue")
        queues = self.storage.list_queues()
        for queue in queues:
            table.add_row(queue.name)
        if queues:
            # Don't rely solely on RowHighlighted firing for the initial
            # cursor position (focus timing can vary once Header/Footer
            # siblings are present) — select the first queue explicitly
            # so the right panel is deterministically populated on open.
            await self._show_queue(queues[0].id)
        # set_interval accepts an async callback directly (confirmed live
        # with a standalone sandbox script — no run_worker wrapper needed).
        self.set_interval(2.0, self._refresh_current)

    async def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # RowHighlighted fires on arrow-key movement (confirmed live: no
        # Enter needed), unlike RowSelected which only fires on
        # Enter/click — this is what makes switching immediate, per the
        # design.
        queues = self.storage.list_queues()
        if event.cursor_row >= len(queues):
            return
        await self._show_queue(queues[event.cursor_row].id)

    async def _show_queue(self, queue_id: int) -> None:
        self._current_queue_id = queue_id
        if queue_id not in self._cache:
            queue = self.storage.get_queue(queue_id)
            path = find_transcript_path(queue.session_id)
            self._cache[queue_id] = {"path": path, "offset": 0, "events": []}
            if path is not None:
                events, offset = parse_transcript_events(path)
                self._cache[queue_id]["events"] = events
                self._cache[queue_id]["offset"] = offset
        await self._render_transcript(queue_id)

    async def _render_transcript(self, queue_id: int) -> None:
        container = self.query_one("#conversation-transcript", VerticalScroll)
        await container.remove_children()
        events: list[TranscriptEvent] = self._cache[queue_id]["events"]
        if not events:
            await container.mount(Static("No conversation yet."))
            return
        for event in events:
            await container.mount(self._render_event(event))

    def _render_event(self, event: TranscriptEvent) -> Static:
        # event.text is arbitrary conversation content (human-typed or a
        # model's tool input/reply) interpolated into a Rich markup
        # string — it must be escaped, or text that happens to contain
        # something like "[red]..." gets interpreted as a style tag
        # instead of shown literally (confirmed: it silently vanishes
        # from the rendered output). Only the fixed label/timestamp
        # around it are intentional markup.
        safe_text = escape(event.text)
        if event.kind == "tool_call":
            return Static(f"⚙ {safe_text}", classes="tool-call-line")
        label = "You" if event.kind == "human" else "Claude"
        box_class = "message-box-human" if event.kind == "human" else "message-box-assistant"
        time_str = event.timestamp.strftime("%H:%M")
        return Static(f"[b]{label}[/b]  [dim]{time_str}[/dim]\n{safe_text}", classes=f"message-box {box_class}")

    async def _refresh_current(self) -> None:
        if self._current_queue_id is None:
            return
        queue_id = self._current_queue_id
        cached = self._cache.get(queue_id)
        if cached is None or cached["path"] is None:
            return
        new_events, new_offset = parse_transcript_events(cached["path"], since_byte_offset=cached["offset"])
        if new_events:
            cached["events"].extend(new_events)
            cached["offset"] = new_offset
            await self._render_transcript(queue_id)

    def action_back(self) -> None:
        self.app.pop_screen()
