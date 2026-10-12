"""Shared look for every cc-continue screen.

The conversations view (left sidebar: app title, rule, section label,
selectable list, coloured action buttons at the bottom; right: content in
round-bordered boxes) is the reference design. Every top-level screen
subclasses SidebarScreen so they all share that frame, and adds its own
sidebar section / main content / buttons through the hooks below.
"""
from __future__ import annotations

from dataclasses import dataclass

from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Rule, Static

from cc_continue.models import QueueStatus


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
    ("sessions", "Live sessions", "s"),
    ("analytics", "Analytics", "v"),
]

ADD_PROMPT_BUTTON = SidebarButton("sidebar-add-prompt", "Add prompt (a)", "green", "add_prompt")
LIVE_SESSIONS_BUTTON = SidebarButton("sidebar-live-sessions", "Live sessions (s)", "blue", "pick_session")
RETRY_BUTTON = SidebarButton("sidebar-retry", "Retry blocked (r)", "red", "retry_queue")
NEW_CONVERSATION_BUTTON = SidebarButton(
    "sidebar-new-conversation", "New conversation (n)", "green", "new_conversation"
)

STATUS_STYLES = {
    QueueStatus.IDLE: "dim",
    QueueStatus.RUNNING: "bold green",
    QueueStatus.WAITING_RETRY: "bold yellow",
    QueueStatus.BLOCKED_ERROR: "bold red",
}


def styled_status(status: QueueStatus) -> str:
    """Rich markup for a queue status cell (status values are a fixed enum,
    so no escaping needed)."""
    style = STATUS_STYLES.get(status, "")
    return f"[{style}]{status.value}[/]" if style else status.value


SHARED_CSS = """
SidebarScreen #sidebar {
    width: 32;
    background: $surface;
}
SidebarScreen .sidebar-title {
    padding: 1 1 0 1;
    text-style: bold;
    color: green;
}
SidebarScreen .sidebar-rule {
    color: yellow;
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

    BINDINGS = [
        ("d", "goto('dashboard')", "Dashboard"),
        ("c", "goto('conversations')", "Conversations"),
        ("s", "goto('sessions')", "Live sessions"),
        ("v", "goto('analytics')", "Analytics"),
        ("a", "add_prompt", "Add prompt"),
        ("n", "new_conversation", "New conversation"),
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
        return [ADD_PROMPT_BUTTON, LIVE_SESSIONS_BUTTON]

    # --- frame -----------------------------------------------------------

    def compose(self):
        yield Header()
        nav_items = []
        for key, label, hotkey in VIEWS:
            item = Static(f"{label}  [dim]{hotkey}[/dim]", id=f"nav-{key}", classes="nav-item")
            if key == self.VIEW:
                item.add_class("-active")
            nav_items.append(item)
        yield Horizontal(
            Vertical(
                Static("cc-continue", classes="sidebar-title"),
                Rule(classes="sidebar-rule"),
                Static("Views", classes="sidebar-label"),
                Vertical(*nav_items, id="sidebar-nav"),
                Vertical(*self.compose_sidebar_section(), id="sidebar-section"),
                *[self._make_button(b) for b in self.sidebar_buttons()],
                id="sidebar",
            ),
            Vertical(*self.compose_main(), id="main"),
        )
        yield Footer()

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
            from cc_continue.tui.dashboard import DashboardScreen

            return DashboardScreen(self.storage)
        if view == "conversations":
            from cc_continue.tui.conversations import ConversationsScreen

            return ConversationsScreen(self.storage, **kwargs)
        if view == "sessions":
            from cc_continue.tui.session_picker import SessionPickerScreen

            return SessionPickerScreen(self.storage)
        if view == "analytics":
            from cc_continue.tui.analytics import AnalyticsScreen

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
        from cc_continue.tui.dashboard import DashboardScreen

        stack = self.app.screen_stack
        home_index = next((i for i, s in enumerate(stack) if isinstance(s, DashboardScreen)), None)
        if home_index is not None:
            for _ in range(len(stack) - 1 - home_index):
                self.app.pop_screen()
            if view != "dashboard":
                self.app.push_screen(screen)
        else:
            self.app.switch_screen(screen)

    def action_new_conversation(self) -> None:
        from cc_continue.tui.new_conversation import NewConversationModal

        def opened(queue_id: int | None) -> None:
            if queue_id is not None:
                self.open_conversation(queue_id)

        self.app.push_screen(NewConversationModal(self.storage), opened)

    def open_conversation(self, queue_id: int) -> None:
        self._navigate("conversations", self._make_view("conversations", select_queue_id=queue_id))

    def action_pick_session(self) -> None:
        self.action_goto("sessions")

    def action_add_prompt(self) -> None:
        from cc_continue.tui.queue_detail import AddPromptModal

        self.app.push_screen(AddPromptModal(self.storage, self.default_project_path()))

    def default_project_path(self) -> str:
        """Prefill for the Add-prompt dialog: the currently selected queue's
        project, where the screen has one."""
        return ""

    def action_back(self) -> None:
        if len(self.app.screen_stack) > 2:
            self.app.pop_screen()
