from __future__ import annotations

import asyncio

from rich.segment import Segment
from rich.text import Text
from textual.containers import Container, Horizontal
from textual.content import Content
from textual.geometry import Region, Size
from textual.reactive import var
from textual.screen import ModalScreen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Button, DataTable, Input, Static, TextArea

from ccc import keymap
from ccc.diff_comments import ADDED, HUNK, META, QUOTE_MAX_CHARS, REMOVED, Comment, parse, prompt
from ccc.i18n import _
from ccc.launch_options import describe_flags
from ccc.models import DeliveryMode, QueueStatus, RunStatus
from ccc.orchestrator import enqueue_prompt
from ccc.storage import Storage
from ccc.tui.layout import (
    ADD_PROMPT_BUTTON,
    MODAL_CSS,
    ConfirmModal,
    RETRY_BUTTON,
    SidebarScreen,
    panel,
    styled_status,
)

def run_status_text(status: RunStatus) -> str:
    return {
        RunStatus.SUCCESS: _("success"),
        RunStatus.RATE_LIMITED: _("rate_limited"),
        RunStatus.ERROR: _("error"),
    }.get(status, status.value)


def delivery_text(mode: DeliveryMode) -> str:
    return {
        DeliveryMode.HEADLESS: _("headless"),
        DeliveryMode.INTERACTIVE: _("interactive"),
        DeliveryMode.LIVE_TERMINAL: _("live_terminal"),
        DeliveryMode.REMOTE_CONTROL: _("remote_control"),
    }.get(mode, mode.value)


RUN_STATUS_STYLES = {
    RunStatus.SUCCESS: "green",
    RunStatus.ERROR: "bold red",
    RunStatus.RATE_LIMITED: "yellow",
}


class AddPromptModal(ModalScreen):
    DEFAULT_CSS = MODAL_CSS.format(cls="AddPromptModal")

    BINDINGS = [keymap.binding("window.cancel", "cancel", _("Cancel"))]

    def __init__(self, storage: Storage, default_path: str = ""):
        super().__init__()
        self.storage = storage
        self.default_path = default_path

    def compose(self):
        box = Container(
            Static(_("Project path"), classes="modal-label"),
            Input(value=self.default_path, placeholder=_("/path/to/project"), id="add-prompt-path"),
            Static(_("Prompt"), classes="modal-label"),
            TextArea(id="add-prompt-text"),
            Static("", id="add-prompt-error", classes="modal-error"),
            Horizontal(
                Button(_("Add"), id="add-prompt-submit", classes="modal-submit"),
                Button(_("Cancel"), id="add-prompt-cancel", classes="modal-cancel"),
                classes="modal-buttons",
            ),
        )
        box.border_title = _("New prompt")
        yield box

    def on_mount(self) -> None:
        # Path is usually prefilled from the selected queue — start in the
        # prompt box then, so you can just type.
        if self.default_path:
            self.query_one("#add-prompt-text", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-prompt-submit":
            path = self.query_one("#add-prompt-path", Input).value.strip()
            prompt = self.query_one("#add-prompt-text", TextArea).text.strip()
            if not path or not prompt:
                self.query_one("#add-prompt-error", Static).update(_("Both path and prompt are required."))
                return
            try:
                enqueue_prompt(self.storage, path, prompt)
            except ValueError as exc:
                self.query_one("#add-prompt-error", Static).update(Content(str(exc)))
                return
            self.dismiss()
        elif event.button.id == "add-prompt-cancel":
            self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()


class DiffView(ScrollView, can_focus=True):
    """A diff, one line per row, with a line cursor (↑↓, PgUp/PgDn, Home/End,
    click) and a ● in front of lines you commented on."""

    COMPONENT_CLASSES = {"diff--added", "diff--removed", "diff--hunk", "diff--meta", "diff--header",
                         "diff--cursor", "diff--marker"}
    DEFAULT_CSS = """
    DiffView { height: 1fr; }
    DiffView > .diff--added { color: $success; }
    DiffView > .diff--removed { color: $error; }
    DiffView > .diff--hunk { color: $accent; }
    DiffView > .diff--meta { color: $text; text-style: bold; }
    DiffView > .diff--header { color: $text-muted; }
    DiffView > .diff--cursor { background: $boost; text-style: reverse; }
    DiffView > .diff--marker { color: $warning; text-style: bold; }
    """
    # Fixed navigation keys, like a DataTable's (not in the keymap).
    _MOVES = {"up": -1, "down": 1, "home": -1_000_000, "end": 1_000_000}

    cursor = var(0)

    def __init__(self, lines, **kwargs):
        super().__init__(**kwargs)
        self.lines = lines
        self.commented: set[int] = set()
        self._texts = [line.text.expandtabs(4) for line in lines]
        width = max((len(t) for t in self._texts), default=0) + 2
        self.virtual_size = Size(width, len(lines))
        # Start on the first changed line rather than the commit header.
        self.cursor = next((i for i, line in enumerate(lines) if line.commentable), 0)

    @property
    def current(self):
        return self.lines[self.cursor] if self.lines else None

    def move_cursor(self, delta: int) -> None:
        self.cursor = max(0, min(len(self.lines) - 1, self.cursor + delta))

    def on_key(self, event) -> None:
        page = max(1, self.size.height - 1)
        delta = {**self._MOVES, "pageup": -page, "pagedown": page}.get(event.key)
        if delta is not None:
            event.stop()
            event.prevent_default()
            self.move_cursor(delta)

    def watch_cursor(self, old: int, new: int) -> None:
        self.scroll_to_region(Region(0, new, 1, 1), animate=False, x_axis=False)
        self.refresh()

    def on_click(self, event) -> None:
        row = event.y + self.scroll_offset.y
        if 0 <= row < len(self.lines):
            self.cursor = row

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        index = y + scroll_y
        width = max(self.virtual_size.width, self.size.width)
        if index >= len(self.lines):
            return Strip.blank(self.size.width)
        kind = self.lines[index].kind
        style = self.get_component_rich_style({
            ADDED: "diff--added", REMOVED: "diff--removed", HUNK: "diff--hunk", META: "diff--meta",
        }.get(kind, "diff--header"))
        if index == self.cursor:
            style += self.get_component_rich_style("diff--cursor")
        marker = Segment("● ", self.get_component_rich_style("diff--marker")) if index in self.commented \
            else Segment("  ", style)
        text = self._texts[index]
        strip = Strip([marker, Segment(text.ljust(width - 2), style)], width)
        return strip.crop(scroll_x, scroll_x + self.size.width)


class CommentModal(ModalScreen):
    """One comment on one diff line: Enter keeps it, an empty one removes
    it, Esc changes nothing."""

    DEFAULT_CSS = MODAL_CSS.format(cls="CommentModal") + """
    CommentModal .diff-comment-hint {
        color: $text-muted;
    }
    """
    BINDINGS = [keymap.binding("window.cancel", "cancel", _("Cancel"))]

    def __init__(self, where: str, code: str, text: str = ""):
        super().__init__()
        self.where, self.code, self.text = where, code, text

    def compose(self):
        box = Container(
            Static(Content(self.code[:QUOTE_MAX_CHARS]), classes="modal-label"),
            Input(value=self.text, placeholder=_("What should Claude change here?"), id="diff-comment-input"),
            Static(_("Enter keeps the comment (empty removes it) · Esc cancels"), classes="diff-comment-hint"),
        )
        box.border_title = self.where
        yield box

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class DiffModal(ModalScreen):
    """`git show` of one auto-commit, coloured, with a line cursor. c
    comments on the line, s sends all comments to the conversation as one
    prompt (ccc.diff_comments)."""

    DEFAULT_CSS = MODAL_CSS.format(cls="DiffModal") + """
    DiffModal > Container {
        width: 95%;
        height: 90%;
    }
    DiffModal #diff-comments {
        height: auto;
        max-height: 8;
        color: $warning;
    }
    """

    BINDINGS = [
        keymap.binding("window.cancel", "close", _("Close")),
        keymap.binding("diff.comment", "comment", _("Comment")),
        keymap.binding("diff.send", "send", _("Send to Claude")),
    ]

    def __init__(self, project_path: str, commit: str, storage: Storage | None = None,
                 queue_id: int | None = None, task: str = ""):
        super().__init__()
        self.project_path = project_path
        self.commit = commit
        self.storage = storage
        self.queue_id = queue_id
        self.task_text = task
        self.comments: dict[int, Comment] = {}

    def compose(self):
        from ccc import gitops

        text = gitops.show(self.project_path, self.commit)
        self.diff_text = text
        box = Container(DiffView(parse(text), id="diff-text"), Static("", id="diff-comments"))
        box.border_title = self._title()
        yield box

    def on_mount(self) -> None:
        self.query_one(DiffView).focus()
        if self.comments:
            self._refresh_comments()

    def _title(self) -> str:
        title = _("Commit {commit}  ·  c comment  ·  s send to Claude  ·  Esc close").format(commit=self.commit[:10])
        if self.comments:
            title += "  ·  " + _("{n} comment(s)").format(n=len(self.comments))
        return title

    def _refresh_comments(self) -> None:
        view = self.query_one(DiffView)
        view.commented = set(self.comments)
        view.refresh()
        listing = [Content.assemble(("● ", "bold"), (c.where + ": ", "bold"), c.text)
                   for _i, c in sorted(self.comments.items())]
        self.query_one("#diff-comments", Static).update(Content("\n").join(listing))
        self.query_one(Container).border_title = self._title()

    def action_comment(self) -> None:
        view = self.query_one(DiffView)
        index, line = view.cursor, view.current
        if line is None or not line.commentable:
            self.notify(_("Move to a changed line of a file first."), severity="warning")
            return
        existing = self.comments.get(index)
        where = Comment(line, "").where

        def done(text: str | None) -> None:
            if text is None:
                return
            if text.strip():
                self.comments[index] = Comment(line, text.strip())
            else:
                self.comments.pop(index, None)
            self._refresh_comments()

        self.app.push_screen(CommentModal(where, line.text, existing.text if existing else ""), done)

    def action_send(self) -> None:
        if not self.comments:
            self.notify(_("No comments yet — c comments on the line under the cursor."), severity="warning")
            return
        if self.storage is None or self.queue_id is None:
            return
        comments = [c for _i, c in sorted(self.comments.items())]
        self.storage.add_queue_item(self.queue_id, prompt(self.commit, self.task_text, comments))
        self.notify(_("{n} comment(s) queued for Claude.").format(n=len(comments)), title=_("Review sent"))
        self.comments.clear()
        self.dismiss()

    def action_close(self) -> None:
        if not self.comments:
            self.dismiss()
            return

        def answered(yes: bool) -> None:
            if yes:
                self.dismiss()

        self.app.push_screen(ConfirmModal(
            _("Discard comments?"),
            _("{n} comment(s) haven't been sent to Claude (s). Close and lose them?").format(n=len(self.comments))),
            answered)


def _commit_cell(run) -> Text:
    if not run.git_commit:
        return Text("—" if not run.git_note else "·", style="dim")
    if run.reverted_by:
        return Text(f"{run.git_commit[:7]} ↺", style="dim strike")
    return Text(run.git_commit[:7])


class QueueDetailScreen(SidebarScreen):
    """Detail of one queue, opened from the dashboard; shares the
    dashboard's sidebar highlight since it's a drill-down of it."""

    VIEW = "dashboard"
    IS_DETAIL = True
    SUB_TITLE = _("Queue detail")

    BINDINGS = [
        keymap.binding("screen.back", "back", _("Back")),
        keymap.binding("screen.retry", "retry_queue", _("Retry blocked"), show=False),
        keymap.binding("screen.add_prompt", "add_prompt", _("Add prompt"), show=False),
        keymap.binding("screen.review", "review", _("Review")),
        keymap.binding("screen.goal", "goal", _("Goal")),
        keymap.binding("screen.workflow", "workflow", _("Workflow")),
        keymap.binding("queue_detail.revert", "revert_run", _("Revert run")),
    ]

    def __init__(self, storage: Storage, queue_id: int):
        super().__init__(storage)
        self.queue_id = queue_id

    def sidebar_buttons(self):
        return [ADD_PROMPT_BUTTON, RETRY_BUTTON]

    def retry_target(self):
        return self.storage.find_queue(self.queue_id)

    def compose_main(self):
        queue = self.storage.get_queue(self.queue_id)
        yield panel(
            Static(Content.assemble((queue.name, "bold"), "  ", (queue.project_path, "dim")), id="queue-detail-title"),
            Static(id="queue-detail-info"),
            title=_("Queue"),
        )
        yield panel(DataTable(id="queue-history-table"), title=_("Run history"), fill=True)

    def on_mount(self) -> None:
        self._refresh_info()
        table = self.query_one("#queue-history-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Started"), _("Status"), _("Tokens"), _("Commit"), _("Result"))
        self._refresh_runs()

    def _refresh_runs(self) -> None:
        table = self.query_one("#queue-history-table", DataTable)
        row = table.cursor_row
        table.clear()
        self._runs = self.storage.runs_for_queue(self.queue_id)
        for run in self._runs:
            tokens = run.input_tokens + run.output_tokens + run.cache_read_tokens + run.cache_creation_tokens
            style = RUN_STATUS_STYLES.get(run.status, "")
            status = f"[{style}]{run_status_text(run.status)}[/]" if style else run_status_text(run.status)
            table.add_row(
                run.started_at.strftime("%Y-%m-%d %H:%M"),
                status,
                f"{tokens:,}",
                _commit_cell(run),
                Text((run.result_text or run.error_text or "")[:60].replace("\n", " ")),
            )
        if self._runs and row is not None:
            table.move_cursor(row=min(row, len(self._runs) - 1))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "queue-history-table" or event.cursor_row >= len(self._runs):
            return
        run = self._runs[event.cursor_row]
        if run.git_commit:
            queue = self.storage.get_queue(self.queue_id)
            task = (run.prompt_text.strip().splitlines() or [""])[0][:200]
            self.app.push_screen(DiffModal(queue.project_path, run.git_commit, self.storage, self.queue_id, task))
        elif run.git_note:
            self.notify(run.git_note, title=_("No commit"))

    def action_revert_run(self) -> None:
        """Revert the selected run's commit (ccc.revert), after asking."""
        from ccc import revert

        row = self.query_one("#queue-history-table", DataTable).cursor_row
        if row is None or row >= len(self._runs):
            return
        run = self._runs[row]
        try:
            revert.check(self.storage, run)
        except revert.RevertError as error:
            self.notify(str(error), title=_("Not reverted"), severity="warning")
            return

        def tell(yes: bool, commit: str) -> None:
            if yes:
                revert.tell_claude(self.storage, run, commit)
                self._refresh_info()

        async def answered(yes: bool) -> None:
            if not yes:
                return
            try:
                commit = await asyncio.to_thread(revert.revert, self.storage, run)
            except revert.RevertError as error:
                self.notify(str(error), title=_("Not reverted"), severity="error")
                return
            self.notify(_("Reverted — commit {commit}.").format(commit=commit[:7]))
            self._refresh_runs()
            self.app.push_screen(ConfirmModal(
                _("Tell Claude?"),
                _("Queue a short note so Claude knows its changes were undone? (Otherwise its next task may still "
                  "assume them.)")), lambda yes: tell(yes, commit))

        task = (run.prompt_text.strip().splitlines() or [""])[0][:80]
        self.app.push_screen(ConfirmModal(
            _("Revert run"),
            _("Undo the commit {commit} of the task “{task}”? ccc makes a new commit that reverts it — nothing is "
              "rewritten, and the revert can be undone too.").format(commit=run.git_commit[:7], task=task)),
            answered)

    def _refresh_info(self) -> None:
        queue = self.storage.get_queue(self.queue_id)
        # Only the first line is markup (fixed enum/number values); the rest
        # carries arbitrary text (errors, session ids) and stays plain.
        auto = _("auto-continue on") if queue.auto_continue else _("auto-continue off")
        lines = [
            Content.from_markup(
                _("Status: {status}   ·   Pending: [b]{pending}[/b]   ·   Delivery: {delivery}").format(
                    status=styled_status(queue.status),
                    pending=self.storage.count_pending_items(queue.id),
                    delivery=delivery_text(queue.delivery_mode),
                )
            ),
            Content(
                _("Launch: {flags}").format(flags=describe_flags(queue.launch_flags)) + f"  ·  {auto}"
                + (_("  ·  queue paused") if queue.paused else "")
            ),
            Content.assemble((_("Session: ") + queue.session_id, "dim")),
        ]
        if queue.delivery_mode == DeliveryMode.REMOTE_CONTROL:
            lines.append(Content.assemble((_("Remote control: "), "bold"), (queue.remote_control_url or _("starting…"), "cyan")))
        if queue.first_run_flags:
            lines.append(Content.assemble((_("First run: ") + " ".join(queue.first_run_flags), "yellow")))
        if queue.next_retry_at:
            lines.append(Content.assemble((_("Next retry: ") + f"{queue.next_retry_at:%Y-%m-%d %H:%M}", "yellow")))
        if queue.last_error:
            lines.append(Content.assemble((_("Last error: ") + queue.last_error[:200], "red")))
        self.query_one("#queue-detail-info", Static).update(Content("\n").join(lines))

    def default_project_path(self) -> str:
        return self.storage.get_queue(self.queue_id).project_path

    def action_retry_queue(self) -> None:
        if self.storage.retry_queue(self.queue_id):
            self._refresh_info()
            self.sync_retry_button()
