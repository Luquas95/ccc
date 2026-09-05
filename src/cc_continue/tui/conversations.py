from __future__ import annotations

from rich.markup import escape
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Rule, Static

from cc_continue.models import QueueStatus
from cc_continue.storage import Storage
from cc_continue.transcript import TranscriptEvent, find_transcript_path, parse_transcript_events


class ConversationsScreen(Screen):
    BINDINGS = [
        ("escape", "back", "Back"),
        ("a", "add_prompt", "Add prompt"),
        ("s", "pick_session", "Live sessions"),
        ("r", "retry_queue", "Retry blocked"),
    ]

    DEFAULT_CSS = """
    ConversationsScreen #conversation-sidebar {
        width: 32;
        background: $surface;
    }
    ConversationsScreen .sidebar-title {
        padding: 1 1 0 1;
        text-style: bold;
        color: green;
    }
    ConversationsScreen .sidebar-rule {
        color: yellow;
    }
    ConversationsScreen .sidebar-label {
        padding: 0 1 1 1;
        text-style: bold;
    }
    ConversationsScreen #conversation-queue-list {
        height: 1fr;
    }
    ConversationsScreen #conversation-queue-list > .datatable--cursor {
        background: blue;
        color: white;
        text-style: bold;
    }
    ConversationsScreen .sidebar-button {
        width: 100%;
        height: 3;
        border: none;
        text-style: bold;
    }
    ConversationsScreen #sidebar-add-prompt {
        background: green;
        color: black;
    }
    ConversationsScreen #sidebar-live-sessions {
        background: blue;
        color: white;
    }
    ConversationsScreen #sidebar-retry {
        background: red;
        color: white;
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
            Vertical(
                Static("cc-continue", classes="sidebar-title"),
                Rule(classes="sidebar-rule"),
                Static("Queues", classes="sidebar-label"),
                DataTable(id="conversation-queue-list"),
                Button("Add prompt (a)", id="sidebar-add-prompt", classes="sidebar-button"),
                Button("Live sessions (s)", id="sidebar-live-sessions", classes="sidebar-button"),
                Button("Retry blocked (r)", id="sidebar-retry", classes="sidebar-button"),
                id="conversation-sidebar",
            ),
            VerticalScroll(id="conversation-transcript"),
        )
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#conversation-queue-list", DataTable)
        table.cursor_type = "row"
        table.show_header = False
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sidebar-add-prompt":
            self.action_add_prompt()
        elif event.button.id == "sidebar-live-sessions":
            self.action_pick_session()
        elif event.button.id == "sidebar-retry":
            self.action_retry_queue()

    def action_add_prompt(self) -> None:
        from cc_continue.tui.queue_detail import AddPromptModal

        self.app.push_screen(AddPromptModal(self.storage))

    def action_pick_session(self) -> None:
        from cc_continue.tui.session_picker import SessionPickerScreen

        self.app.push_screen(SessionPickerScreen(self.storage))

    def action_retry_queue(self) -> None:
        if self._current_queue_id is None:
            return
        queue = self.storage.get_queue(self._current_queue_id)
        if queue.status == QueueStatus.BLOCKED_ERROR:
            # No in-process runtime to notify (this screen never executes
            # anything) — flipping the status is enough, the daemon picks
            # it up on its next poll.
            self.storage.update_queue_status(queue.id, QueueStatus.IDLE)

    def action_back(self) -> None:
        self.app.pop_screen()
