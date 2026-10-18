"""Shared look for every ccc screen.

The conversations view (left sidebar: app title, rule, section label,
selectable list, coloured action buttons at the bottom; right: content in
round-bordered boxes) is the reference design. Every top-level screen
subclasses SidebarScreen so they all share that frame, and adds its own
sidebar section / main content / buttons through the hooks below.
"""
from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Rule, Static

from ccc.models import Queue, QueueStatus


@dataclass(frozen=True)
class SidebarButton:
    id: str
    # Fixed, hardcoded labels only — Button labels are parsed as Rich
    # markup, so use "(a)" rather than "[a]" (brackets get silently eaten).
    label: str
    color: str  # "green" | "blue" | "red" — see .sidebar-button-* CSS
    action: str  # action name on the screen, without the "action_" prefix


# (view key, label, hotkey) in sidebar order.
VIEWS: list[tuple[str, str, str]] = [
    ("dashboard", "Dashboard", "d"),
    ("conversations", "Conversations", "c"),
    ("archive", "Archive", "h"),
    ("sessions", "Live sessions", "s"),
    ("analytics", "Analytics", "v"),
]

ADD_PROMPT_BUTTON = SidebarButton("sidebar-add-prompt", "Add prompt (a)", "green", "add_prompt")
RETRY_BUTTON = SidebarButton("sidebar-retry", "Retry blocked queue (r)", "red", "retry_queue")
# What r (and the retry button) can get going again.
RETRYABLE = (QueueStatus.BLOCKED_ERROR, QueueStatus.PAUSED_LIMIT)
NEW_CONVERSATION_BUTTON = SidebarButton(
    "sidebar-new-conversation", "New conversation (n)", "green", "new_conversation"
)

STATUS_STYLES = {
    QueueStatus.IDLE: "dim",
    QueueStatus.RUNNING: "bold green",
    QueueStatus.WAITING_RETRY: "bold yellow",
    QueueStatus.BLOCKED_ERROR: "bold red",
    QueueStatus.PAUSED_LIMIT: "bold magenta",
}


def styled_status(status: QueueStatus) -> str:
    """Rich markup for a queue status cell (status values are a fixed enum,
    so no escaping needed)."""
    style = STATUS_STYLES.get(status, "")
    return f"[{style}]{status.value}[/]" if style else status.value


def queue_marker(queue: Queue, unseen: bool, needs_approval: bool = False) -> tuple[str, str]:
    """(icon, style) shown before a conversation's name. Waiting for your
    approval first, then current activity, then the "new reply" marker."""
    if needs_approval:
        return "?", "bold yellow"
    if queue.status == QueueStatus.RUNNING:
        return "●", "bold green"
    if queue.status == QueueStatus.BLOCKED_ERROR:
        return "✖", "bold red"
    if queue.status in (QueueStatus.PAUSED_LIMIT, QueueStatus.WAITING_RETRY):
        return "‖", "bold magenta"
    if queue.paused:
        return "‖", "bold yellow"
    if unseen:
        return "◆", "bold cyan"
    return " ", ""


def queue_label(queue: Queue, unseen: bool, pending: int = 0, needs_approval: bool = False) -> Text:
    """List label: marker, name (dim when archived), pending count."""
    icon, style = queue_marker(queue, unseen, needs_approval)
    label = Text.assemble((icon, style), " ", (queue.name, "dim" if queue.archived else ""))
    if pending:
        label.append(f" ·{pending}", style="dim")
    return label


class ConfirmModal(ModalScreen):
    """Yes/no question. Dismisses True only when confirmed; with
    can_confirm=False it's just a notice (any key closes it, False)."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    ConfirmModal > Vertical {
        width: 70;
        height: auto;
        border: round red;
        border-title-color: red;
        border-title-style: bold;
        background: $surface;
        padding: 1 2;
    }
    ConfirmModal .confirm-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("y", "answer(True)", "Yes"),
        ("enter", "answer(True)", "Yes"),
        ("n", "answer(False)", "No"),
        ("escape", "answer(False)", "No"),
    ]

    def __init__(self, title: str, text: str, can_confirm: bool = True):
        super().__init__()
        self.box_title = title
        self.text = text
        self.can_confirm = can_confirm

    def compose(self):
        hint = "y / Enter yes  ·  n / Esc no" if self.can_confirm else "Esc close"
        box = Vertical(Static(Text(self.text), id="confirm-text"), Static(hint, classes="confirm-hint"))
        box.border_title = self.box_title
        yield box

    def action_answer(self, yes: bool) -> None:
        self.dismiss(yes and self.can_confirm)


SHARED_CSS = """
SidebarScreen #sidebar {
    width: 32;
    background: $surface;
}
SidebarScreen #daemon-state {
    padding: 0 1;
}
SidebarScreen .sidebar-title {
    padding: 1 1 0 1;
    text-style: bold;
    color: green;
}
SidebarScreen .sidebar-rule {
    color: yellow;
    margin-bottom: 1;
}
SidebarScreen .sidebar-label {
    padding: 0 1 1 1;
    text-style: bold;
}
SidebarScreen .nav-item {
    padding: 0 1;
    height: 1;
}
SidebarScreen .nav-item:hover {
    background: $boost;
}
SidebarScreen .nav-item.-active {
    background: blue;
    color: white;
    text-style: bold;
}
SidebarScreen #sidebar-nav {
    height: auto;
    margin-bottom: 1;
}
SidebarScreen #sidebar-section {
    height: 1fr;
}
SidebarScreen .sidebar-list {
    height: 1fr;
}
SidebarScreen #sidebar DataTable.sidebar-list > .datatable--cursor {
    background: blue;
    color: white;
    text-style: bold;
}
SidebarScreen #sidebar Button.sidebar-button {
    width: 100%;
    height: 3;
    border: none;
    text-style: bold;
}
SidebarScreen #sidebar Button.sidebar-button-green {
    background: green;
    color: black;
}
SidebarScreen #sidebar Button.sidebar-button-blue {
    background: blue;
    color: white;
}
SidebarScreen #sidebar Button.sidebar-button-red {
    background: red;
    color: white;
}
SidebarScreen #main {
    width: 1fr;
    padding: 0 1;
}
SidebarScreen .panel {
    border: round cyan;
    border-title-color: green;
    border-title-style: bold;
    padding: 0 1;
    margin-bottom: 1;
    height: auto;
}
SidebarScreen .panel-fill {
    height: 1fr;
}
SidebarScreen .panel DataTable {
    height: auto;
    max-height: 100%;
}
SidebarScreen .panel-fill DataTable {
    height: 1fr;
}
SidebarScreen .panel DataTable > .datatable--cursor {
    background: blue;
    color: white;
    text-style: bold;
}
SidebarScreen .muted {
    color: $text-muted;
}
"""

# Same frame for modal dialogs: a round green box with the title in the
# border, coloured Submit/Cancel buttons matching the sidebar ones.
MODAL_CSS = """
{cls} {{
    align: center middle;
}}
{cls} > Container {{
    width: 84;
    height: auto;
    border: round green;
    border-title-color: green;
    border-title-style: bold;
    background: $surface;
    padding: 1 2;
}}
{cls} Input {{
    margin-bottom: 1;
}}
{cls} TextArea {{
    height: 8;
    margin-bottom: 1;
}}
{cls} .modal-label {{
    text-style: bold;
}}
{cls} .modal-error {{
    color: red;
}}
{cls} .modal-buttons {{
    height: 3;
    align-horizontal: right;
}}
{cls} .modal-buttons Button {{
    border: none;
    height: 3;
    margin-left: 1;
    text-style: bold;
}}
{cls} .modal-submit {{
    background: green;
    color: black;
}}
{cls} .modal-cancel {{
    background: red;
    color: white;
}}
"""


def panel(*children, title: str, id: str | None = None, fill: bool = False) -> Vertical:
    """A round-bordered content box with its title drawn in the border —
    the main-pane equivalent of the conversation message boxes."""
    box = Vertical(*children, id=id, classes="panel panel-fill" if fill else "panel")
    box.border_title = title
    return box


class SidebarScreen(Screen):
    """Base for all top-level screens. Subclasses set VIEW (which sidebar
    nav item is highlighted), SUB_TITLE, and override compose_main() and
    optionally compose_sidebar_section() / sidebar_buttons()."""

    VIEW: str = ""

    DEFAULT_CSS = SHARED_CSS

    # The footer only shows what the sidebar doesn't: views and the
    # sidebar buttons have their hotkey printed right next to them.
    # The buttons are only the extra controls of the current view —
    # switching views is the nav list's job, not a button's. A view's own
    # keys (like "a" for its Add prompt button) live in that view only.
    BINDINGS = [
        Binding("d", "goto('dashboard')", "Dashboard", show=False),
        Binding("c", "goto('conversations')", "Conversations", show=False),
        Binding("h", "goto('archive')", "Archive", show=False),
        Binding("s", "goto('sessions')", "Live sessions", show=False),
        Binding("v", "goto('analytics')", "Analytics", show=False),
        Binding("n", "new_conversation", "New conversation", show=False),
        Binding("question_mark", "key_help", "Help"),
    ]

    def __init__(self, storage):
        super().__init__()
        self.storage = storage

    # --- hooks -----------------------------------------------------------

    def compose_sidebar_section(self):
        """Extra widgets between the nav list and the buttons."""
        return []

    def compose_main(self):
        return []

    def sidebar_buttons(self) -> list[SidebarButton]:
        return []

    def retry_target(self) -> Queue | None:
        """The queue the retry button acts on (the selected one)."""
        return None

    # --- frame -----------------------------------------------------------

    def compose(self):
        yield Header(icon=" ")
        nav_items = []
        for key, label, hotkey in VIEWS:
            item = Static(f"{label}  [dim]{hotkey}[/dim]", id=f"nav-{key}", classes="nav-item")
            if key == self.VIEW:
                item.add_class("-active")
            nav_items.append(item)
        yield Horizontal(
            Vertical(
                Static("ccc", classes="sidebar-title"),
                Static("", id="daemon-state"),
                Rule(classes="sidebar-rule"),
                Vertical(*nav_items, id="sidebar-nav"),
                Vertical(*self.compose_sidebar_section(), id="sidebar-section"),
                *[self._make_button(b) for b in self.sidebar_buttons()],
                id="sidebar",
            ),
            Vertical(*self.compose_main(), id="main"),
        )
        yield Footer()

    def on_screen_resume(self) -> None:
        self.refresh_daemon_state()

    def sync_retry_button(self) -> None:
        """Show the retry button only while there is something to retry."""
        buttons = self.query(f"#{RETRY_BUTTON.id}")
        if buttons:
            target = self.retry_target()
            buttons.first().display = target is not None and target.status in RETRYABLE

    def on_mount(self) -> None:
        # Textual dispatches on_mount along the MRO, so this runs in
        # addition to each screen's own on_mount.
        self.refresh_daemon_state()
        self.set_interval(2.0, self.refresh_daemon_state)
        if getattr(self.app, "footer_strip", False):
            # The keys are in the strip under the whole window (footer_strip).
            self.query_one(Footer).display = False

    def refresh_daemon_state(self) -> None:
        from ccc.heartbeat import daemon_alive

        if daemon_alive(self.storage):
            text = Text("● daemon running", style="green")
        else:
            text = Text("✖ daemon not running — queues are stopped", style="bold red")
        self.query_one("#daemon-state", Static).update(text)
        self.sync_retry_button()

    @staticmethod
    def _make_button(spec: SidebarButton) -> Button:
        button = Button(spec.label, id=spec.id, classes=f"sidebar-button sidebar-button-{spec.color}")
        # Every button has its own hotkey; keeping them out of the focus
        # chain means initial focus (and Enter) lands on the screen's list,
        # not on whichever button happens to come first in the sidebar.
        button.can_focus = False
        return button

    def on_click(self, event) -> None:
        widget = event.widget
        if widget is not None and widget.has_class("nav-item") and widget.id:
            self.action_goto(widget.id.removeprefix("nav-"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        for button in self.sidebar_buttons():
            if event.button.id == button.id:
                event.stop()
                getattr(self, f"action_{button.action}")()
                return

    # --- navigation ------------------------------------------------------

    def _make_view(self, view: str, **kwargs) -> Screen:
        if view == "dashboard":
            from ccc.tui.dashboard import DashboardScreen

            return DashboardScreen(self.storage)
        if view == "conversations":
            from ccc.tui.conversations import ConversationsScreen

            return ConversationsScreen(self.storage, **kwargs)
        if view == "archive":
            from ccc.tui.archive import ArchiveScreen

            return ArchiveScreen(self.storage, **kwargs)
        if view == "sessions":
            from ccc.tui.session_picker import SessionPickerScreen

            return SessionPickerScreen(self.storage)
        if view == "analytics":
            from ccc.tui.analytics import AnalyticsScreen

            return AnalyticsScreen(self.storage)
        raise ValueError(f"unknown view: {view}")

    def action_goto(self, view: str) -> None:
        if view == self.VIEW and not getattr(self, "IS_DETAIL", False):
            return
        self._navigate(view, self._make_view(view))

    def _navigate(self, view: str, screen: Screen) -> None:
        """Show another top-level view, keeping the stack shallow:
        dashboard is the home screen at the bottom, at most one other view
        sits on top of it (plus a detail screen pushed from that view)."""
        from ccc.tui.dashboard import DashboardScreen

        stack = self.app.screen_stack
        home_index = next((i for i, s in enumerate(stack) if isinstance(s, DashboardScreen)), None)
        if home_index is not None:
            for _ in range(len(stack) - 1 - home_index):
                self.app.pop_screen()
            if view != "dashboard":
                self.app.push_screen(screen)
        else:
            self.app.switch_screen(screen)

    def action_key_help(self) -> None:
        from ccc.help import VIEW_TOPICS
        from ccc.tui.help import HelpScreen

        self.app.push_screen(HelpScreen(VIEW_TOPICS.get(self.VIEW, "getting-started")))

    def action_new_conversation(self) -> None:
        from ccc.tui.new_conversation import NewConversationModal

        def opened(queue_id: int | None) -> None:
            if queue_id is not None:
                self.open_conversation(queue_id)

        self.app.push_screen(NewConversationModal(self.storage), opened)

    def open_conversation(self, queue_id: int) -> None:
        self._navigate("conversations", self._make_view("conversations", select_queue_id=queue_id))

    def action_add_prompt(self) -> None:
        from ccc.tui.queue_detail import AddPromptModal

        self.app.push_screen(AddPromptModal(self.storage, self.default_project_path()))

    def default_project_path(self) -> str:
        """Prefill for the Add-prompt dialog: the currently selected queue's
        project, where the screen has one."""
        return ""

    def action_back(self) -> None:
        if len(self.app.screen_stack) > 2:
            self.app.pop_screen()
