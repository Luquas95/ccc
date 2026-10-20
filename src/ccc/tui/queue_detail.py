from __future__ import annotations

from rich.text import Text
from textual.containers import Container, Horizontal, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Static, TextArea

from ccc import keymap
from ccc.i18n import _
from ccc.launch_options import describe_flags
from ccc.models import DeliveryMode, QueueStatus, RunStatus
from ccc.orchestrator import enqueue_prompt
from ccc.storage import Storage
from ccc.tui.layout import (
    ADD_PROMPT_BUTTON,
    MODAL_CSS,
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


class DiffModal(ModalScreen):
    """`git show` of one auto-commit, coloured, scrollable."""

    DEFAULT_CSS = MODAL_CSS.format(cls="DiffModal") + """
    DiffModal > Container {
        width: 95%;
        height: 90%;
    }
    DiffModal VerticalScroll {
        height: 1fr;
    }
    """

    BINDINGS = [keymap.binding("window.cancel", "close", _("Close"))]

    def __init__(self, project_path: str, commit: str):
        super().__init__()
        self.project_path = project_path
        self.commit = commit

    def compose(self):
        from rich.syntax import Syntax

        from ccc import gitops

        text = gitops.show(self.project_path, self.commit)
        self.diff_text = text
        diff = Static(Syntax(text, "diff", theme="ansi_dark", word_wrap=False), id="diff-text")
        box = Container(VerticalScroll(diff))
        box.border_title = _("Commit {commit}  ·  Esc close").format(commit=self.commit[:10])
        yield box

    def action_close(self) -> None:
        self.dismiss()


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
        self._runs = self.storage.runs_for_queue(self.queue_id)
        for run in self._runs:
            tokens = run.input_tokens + run.output_tokens + run.cache_read_tokens + run.cache_creation_tokens
            style = RUN_STATUS_STYLES.get(run.status, "")
            status = f"[{style}]{run_status_text(run.status)}[/]" if style else run_status_text(run.status)
            table.add_row(
                run.started_at.strftime("%Y-%m-%d %H:%M"),
                status,
                f"{tokens:,}",
                Text(run.git_commit[:7]) if run.git_commit else Text("—" if not run.git_note else "·", style="dim"),
                Text((run.result_text or run.error_text or "")[:60].replace("\n", " ")),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "queue-history-table" or event.cursor_row >= len(self._runs):
            return
        run = self._runs[event.cursor_row]
        if run.git_commit:
            queue = self.storage.get_queue(self.queue_id)
            self.app.push_screen(DiffModal(queue.project_path, run.git_commit))
        elif run.git_note:
            self.notify(run.git_note, title=_("No commit"))

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
