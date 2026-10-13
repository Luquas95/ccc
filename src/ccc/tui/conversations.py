from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.containers import Vertical, VerticalScroll
from textual.content import Content
from textual.widgets import DataTable, Static

from ccc.launch_options import describe_flags
from ccc.models import DeliveryMode, Queue, QueueStatus
from ccc.storage import Storage
from ccc.transcript import TranscriptEvent, find_transcript_path, parse_transcript_events
from ccc.tui.layout import (
    LIVE_SESSIONS_BUTTON,
    NEW_CONVERSATION_BUTTON,
    RETRY_BUTTON,
    ConfirmModal,
    SidebarScreen,
    queue_label,
)
from ccc.tui.message_box import MessageBox


# Newest transcript events mounted when a conversation is opened; older
# ones are summarised in one line (mounting is ~7ms per message).
MAX_RENDERED_EVENTS = 100


class ConversationsScreen(SidebarScreen):
    VIEW = "conversations"
    SUB_TITLE = "Conversations"

    BINDINGS = [
        ("escape", "back", "Back"),
        ("r", "retry_queue", "Retry / resume"),
        ("t", "tasks", "Tasks"),
        ("x", "toggle_archive", "Archive"),
        ("h", "toggle_show_archived", "Show archived"),
        ("ctrl+d", "delete_conversation", "Delete"),
    ]

    # Sidebar frame/buttons come from SidebarScreen (layout.SHARED_CSS);
    # only the transcript message boxes are specific to this screen.
    DEFAULT_CSS = """
    ConversationsScreen #conversation-header {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }
    ConversationsScreen #conversation-transcript {
        width: 1fr;
        height: 1fr;
    }
    ConversationsScreen #conversation-status {
        height: 1;
        padding: 0 1;
    }
    ConversationsScreen #queued-messages {
        height: auto;
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
    ConversationsScreen .message-box-queued {
        border: round $panel-lighten-2;
        color: $text-muted;
    }
    ConversationsScreen .message-header {
        color: $accent;
    }
    ConversationsScreen .tool-call-line {
        color: $text-muted;
    }
    """

    def __init__(self, storage: Storage, select_queue_id: int | None = None):
        super().__init__(storage)
        # Per-queue cache: queue_id -> {"path": Path|None, "offset": int,
        # "events": list[TranscriptEvent]} so switching back to an
        # already-viewed queue doesn't re-parse its transcript from zero.
        self._cache: dict[int, dict] = {}
        self._current_queue_id: int | None = select_queue_id
        # Opened for a specific (usually just-started) conversation: put the
        # cursor straight into the message box.
        self._focus_input_on_mount = select_queue_id is not None
        # Queue ids in the order of the sidebar table's rows.
        self._queue_ids: list[int] = []
        # Plain text of the list rows as last drawn — rebuild when it changes
        # (new/removed conversation, status marker, pending count).
        self._list_signature: list[str] = []
        self._show_archived = False
        # What the transcript pane currently shows (queue, event count,
        # pending item ids) — re-render only when this changes.
        self._rendered_key: tuple | None = None

    def sidebar_buttons(self):
        return [NEW_CONVERSATION_BUTTON, LIVE_SESSIONS_BUTTON, RETRY_BUTTON]

    def compose_sidebar_section(self):
        yield Static("Queues", classes="sidebar-label")
        yield DataTable(id="conversation-queue-list", classes="sidebar-list")

    def compose_main(self):
        yield Static(id="conversation-header")
        yield VerticalScroll(id="conversation-transcript")
        yield Static(id="conversation-status")
        yield MessageBox(placeholder="Message Claude… (Enter send · Ctrl+J new line · Esc back)", id="message-input")

    async def on_mount(self) -> None:
        table = self.query_one("#conversation-queue-list", DataTable)
        table.cursor_type = "row"
        table.show_header = False
        self._rebuild_queue_list()
        if self._current_queue_id not in self._queue_ids:
            self._current_queue_id = self._queue_ids[0] if self._queue_ids else None
        if self._current_queue_id is not None:
            # Don't rely solely on RowHighlighted firing for the initial
            # cursor position (focus timing can vary once Header/Footer
            # siblings are present) — select the queue explicitly so the
            # right panel is deterministically populated on open.
            self._move_cursor_to_current()
            await self._show_queue(self._current_queue_id)
        # set_interval accepts an async callback directly (confirmed live
        # with a standalone sandbox script — no run_worker wrapper needed).
        self.set_interval(2.0, self._refresh_current)
        if self._focus_input_on_mount:
            self.query_one("#message-input", MessageBox).focus()

    def _rebuild_queue_list(self) -> None:
        table = self.query_one("#conversation-queue-list", DataTable)
        # Recreate the column too: after a plain clear() the auto width
        # stays at the header's ("Queue") and every name gets cut to 5 chars.
        table.clear(columns=True)
        table.add_column("Queue")
        rows = self._list_rows()
        self._queue_ids = [queue_id for queue_id, _ in rows]
        self._list_signature = [label.plain for _, label in rows]
        for _, label in rows:
            table.add_row(label)

    def _list_rows(self) -> list[tuple[int, Text]]:
        unseen = self.storage.unseen_queue_ids()
        return [
            (q.id, queue_label(q, q.id in unseen and q.id != self._current_queue_id,
                               self.storage.count_pending_items(q.id)))
            for q in self.storage.list_queues()
            if self._show_archived or not q.archived
        ]

    def _move_cursor_to_current(self) -> None:
        if self._current_queue_id in self._queue_ids:
            table = self.query_one("#conversation-queue-list", DataTable)
            table.move_cursor(row=self._queue_ids.index(self._current_queue_id))

    async def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # RowHighlighted fires on arrow-key movement (confirmed live: no
        # Enter needed), unlike RowSelected which only fires on
        # Enter/click — this is what makes switching immediate, per the
        # design.
        if event.cursor_row >= len(self._queue_ids):
            return
        queue_id = self._queue_ids[event.cursor_row]
        if queue_id != self._current_queue_id or self._rendered_key is None:
            await self._show_queue(queue_id)

    async def _show_queue(self, queue_id: int) -> None:
        self._current_queue_id = queue_id
        self.storage.mark_seen(queue_id)
        self._load_transcript(queue_id)
        await self._render_transcript(queue_id)

    def _load_transcript(self, queue_id: int) -> bool:
        """Read new transcript lines into the cache. Returns True if any new
        events arrived. A queue whose transcript doesn't exist yet (a new
        conversation before its first run) is looked up again each call."""
        cached = self._cache.setdefault(queue_id, {"path": None, "offset": 0, "events": []})
        if cached["path"] is None:
            cached["path"] = find_transcript_path(self.storage.get_queue(queue_id).session_id)
            if cached["path"] is None:
                return False
        events, offset = parse_transcript_events(cached["path"], since_byte_offset=cached["offset"])
        cached["offset"] = offset
        cached["events"].extend(events)
        return bool(events)

    async def _render_transcript(self, queue_id: int) -> None:
        """Full re-render of the transcript pane (switching queues). Only
        the newest MAX_RENDERED_EVENTS events are mounted — a long resumed
        session has thousands, and mounting each costs ~7ms."""
        queue = self.storage.get_queue(queue_id)
        pending = self.storage.list_pending_items(queue_id)
        events: list[TranscriptEvent] = self._cache[queue_id]["events"]
        self._update_header(queue)
        self.query_one("#conversation-status", Static).update(self._status_text(queue, len(pending)))
        self._rendered_key = (queue_id, len(events), tuple(i.id for i in pending))

        container = self.query_one("#conversation-transcript", VerticalScroll)
        await container.remove_children()
        if not events and not pending:
            await container.mount(Static("No conversation yet.", id="transcript-placeholder"))
            return
        shown = events[-MAX_RENDERED_EVENTS:]
        widgets = []
        if len(events) > len(shown):
            widgets.append(
                Static(f"… {len(events) - len(shown)} earlier messages not shown", classes="tool-call-line")
            )
        widgets += [self._render_event(e) for e in shown]
        widgets.append(Vertical(*self._queued_widgets(pending), id="queued-messages"))
        # One mount call = one layout pass, much faster than mounting
        # each widget separately.
        await container.mount(*widgets)
        container.scroll_end(animate=False)

    async def _append_new_events(self, queue_id: int, new_events: list[TranscriptEvent], pending) -> None:
        """Incremental update while a conversation is open: add only the new
        events (before the queued bubbles) and refresh the queued list,
        instead of re-mounting the whole transcript every 2 seconds."""
        container = self.query_one("#conversation-transcript", VerticalScroll)
        queued_box = self.query_one("#queued-messages", Vertical)
        if new_events:
            await container.mount(*[self._render_event(e) for e in new_events], before=queued_box)
        await queued_box.remove_children()
        await queued_box.mount(*self._queued_widgets(pending))
        container.scroll_end(animate=False)

    @staticmethod
    def _queued_widgets(pending) -> list[Static]:
        return [
            Static(
                Content.assemble(("You", "bold"), "  ", ("queued", "dim"), "\n", item.prompt_text),
                classes="message-box message-box-queued",
            )
            for item in pending
        ]

    def _render_event(self, event: TranscriptEvent) -> Static:
        # event.text is arbitrary conversation content (human-typed or a
        # model's tool input/reply). It must never go through markup
        # parsing: escaping isn't enough — a tool preview cut mid-way
        # through something like `[data-section=\"quick…` crashed
        # Textual's markup parser even after escape(). Content.assemble
        # keeps it as plain text; only the label/timestamp get styles.
        if event.kind == "tool_call":
            return Static(Content.assemble("⚙ ", event.text), classes="tool-call-line")
        label = "You" if event.kind == "human" else "Claude"
        box_class = "message-box-human" if event.kind == "human" else "message-box-assistant"
        # Transcript timestamps are UTC; show local time.
        time_str = event.timestamp.astimezone().strftime("%H:%M")
        return Static(
            Content.assemble((label, "bold"), "  ", (time_str, "dim"), "\n", event.text),
            classes=f"message-box {box_class}",
        )

    def _update_header(self, queue: Queue) -> None:
        parts = [
            (queue.name, "bold"), "  ", (queue.project_path, "dim"), "  ·  ", describe_flags(queue.launch_flags),
            "  ·  ", ("auto-continue on", "green") if queue.auto_continue else ("auto-continue off", "yellow"),
        ]
        if queue.delivery_mode == DeliveryMode.REMOTE_CONTROL:
            parts += ["\n", ("remote control: ", "bold"), (queue.remote_control_url or "starting…", "cyan")]
        if queue.first_run_flags:
            parts += ["  ·  ", ("first run: " + " ".join(queue.first_run_flags), "yellow")]
        self.query_one("#conversation-header", Static).update(Content.assemble(*parts))

    @staticmethod
    def _status_text(queue: Queue, pending: int) -> Content:
        if queue.status == QueueStatus.RUNNING:
            status = ("● Claude is working…", "bold green")
        elif queue.status == QueueStatus.WAITING_RETRY and queue.next_retry_at:
            status = (f"‖ Waiting for usage limit reset until {queue.next_retry_at:%H:%M}", "bold yellow")
        elif queue.status == QueueStatus.PAUSED_LIMIT:
            if queue.next_retry_at and queue.next_retry_at > datetime.now():
                status = (f"‖ Paused at usage limit, resets {queue.next_retry_at:%H:%M}", "bold magenta")
            else:
                status = ("‖ Limit reset — press r to continue", "bold magenta")
        elif queue.paused:
            status = ("‖ Queue paused — t, p to resume", "bold yellow")
        elif queue.status == QueueStatus.BLOCKED_ERROR:
            line = (queue.last_error or "").replace("\n", " ")[:120]
            status = (f"✖ Blocked: {line} — press r to retry", "bold red")
        else:
            status = ("Ready", "dim")
        return Content.assemble(status, f"  ·  {pending} queued" if pending else "")

    async def _refresh_current(self) -> None:
        if self._current_queue_id is not None and self.app.screen is self:
            # You're looking at it: replies to it aren't "new".
            self.storage.mark_seen(self._current_queue_id)
        if [label.plain for _, label in self._list_rows()] != self._list_signature:
            # New/removed conversation, or a marker / pending count changed.
            self._rebuild_queue_list()
            self._move_cursor_to_current()
        if self._current_queue_id is None:
            return
        queue_id = self._current_queue_id
        self._load_transcript(queue_id)
        queue = self.storage.get_queue(queue_id)
        pending = self.storage.list_pending_items(queue_id)
        events = self._cache[queue_id]["events"]
        key = (queue_id, len(events), tuple(i.id for i in pending))
        self._update_header(queue)
        self.query_one("#conversation-status", Static).update(self._status_text(queue, len(pending)))
        if key == self._rendered_key:
            return
        rendered = self._rendered_key
        incremental = (
            rendered is not None
            and rendered[0] == queue_id
            and len(events) >= rendered[1]
            and self.query("#queued-messages")
        )
        if incremental:
            await self._append_new_events(queue_id, events[rendered[1]:], pending)
            self._rendered_key = key
        else:
            await self._render_transcript(queue_id)

    async def on_message_box_submitted(self, event: MessageBox.Submitted) -> None:
        text = event.text.strip()
        if not text or self._current_queue_id is None:
            return
        # Pure storage write — the daemon picks it up on its next poll.
        self.storage.add_queue_item(self._current_queue_id, text)
        if self.storage.get_queue(self._current_queue_id).status == QueueStatus.PAUSED_LIMIT:
            # Writing to a conversation paused at a limit means "go on".
            self.storage.update_queue_status(self._current_queue_id, QueueStatus.IDLE)
        event.box.text = ""
        await self._refresh_current()

    def open_conversation(self, queue_id: int) -> None:
        # Already on this screen: just select it in place.
        self._rebuild_queue_list()
        self._current_queue_id = queue_id
        self._move_cursor_to_current()
        self.run_worker(self._show_queue(queue_id), exclusive=True, group="show-queue")
        self.query_one("#message-input", MessageBox).focus()

    def default_project_path(self) -> str:
        if self._current_queue_id is None:
            return ""
        return self.storage.get_queue(self._current_queue_id).project_path

    def action_retry_queue(self) -> None:
        if self._current_queue_id is None:
            return
        queue = self.storage.get_queue(self._current_queue_id)
        if queue.status in (QueueStatus.BLOCKED_ERROR, QueueStatus.PAUSED_LIMIT):
            # No in-process runtime to notify (this screen never executes
            # anything) — flipping the status is enough, the daemon picks
            # it up on its next poll.
            self.storage.update_queue_status(queue.id, QueueStatus.IDLE)
            self.run_worker(self._refresh_current(), exclusive=True, group="refresh")

    def action_tasks(self) -> None:
        from ccc.tui.tasks import TasksModal

        if self._current_queue_id is None:
            return

        def closed(_result) -> None:
            self.run_worker(self._refresh_current(), exclusive=True, group="refresh")

        self.app.push_screen(TasksModal(self.storage, self._current_queue_id), closed)

    def action_toggle_archive(self) -> None:
        if self._current_queue_id is None:
            return
        queue = self.storage.get_queue(self._current_queue_id)
        self.storage.set_queue_archived(queue.id, not queue.archived)
        if not queue.archived and not self._show_archived:
            self._select_neighbour()
        self.run_worker(self._refresh_current(), exclusive=True, group="refresh")

    def action_toggle_show_archived(self) -> None:
        self._show_archived = not self._show_archived
        self._rebuild_queue_list()
        self._move_cursor_to_current()

    def action_delete_conversation(self) -> None:
        if self._current_queue_id is None:
            return
        queue = self.storage.get_queue(self._current_queue_id)
        if queue.status == QueueStatus.RUNNING:
            self.app.push_screen(
                ConfirmModal(
                    "Can't delete",
                    f"Claude is working on '{queue.name}' right now — wait or pause it first (t, p).",
                    can_confirm=False,
                )
            )
            return

        def answered(yes: bool) -> None:
            if not yes:
                return
            self.storage.delete_queue(queue.id)
            self._cache.pop(queue.id, None)
            self._select_neighbour()
            self.run_worker(self._after_delete(), exclusive=True, group="refresh")

        self.app.push_screen(
            ConfirmModal(
                "Delete conversation",
                f"Delete '{queue.name}' with its queued tasks and run history from ccc?\n"
                "Claude Code's own transcript stays, so it can still be resumed later.",
            ),
            answered,
        )

    def _select_neighbour(self) -> None:
        """Pick the next (else previous) visible conversation after the
        current one disappears from the list."""
        ids = self._queue_ids
        current = self._current_queue_id
        if current in ids:
            i = ids.index(current)
            rest = ids[i + 1:] + list(reversed(ids[:i]))
        else:
            rest = ids
        self._current_queue_id = rest[0] if rest else None
        self._rendered_key = None

    async def _after_delete(self) -> None:
        self._rebuild_queue_list()
        self._move_cursor_to_current()
        if self._current_queue_id is None:
            container = self.query_one("#conversation-transcript", VerticalScroll)
            await container.remove_children()
            await container.mount(Static("No conversation yet."))
            self.query_one("#conversation-header", Static).update("")
            self.query_one("#conversation-status", Static).update("")
            return
        await self._show_queue(self._current_queue_id)
