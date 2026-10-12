from __future__ import annotations

from pathlib import Path

from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DirectoryTree, Input, OptionList, Static
from textual.widgets.option_list import Option

from cc_continue.launch_options import (
    DEFAULT_SELECTION, FORK, GROUPS, SESSION_FROM_PR, SESSION_NEW, SESSION_RESUME, session_mode, toggle,
)
from cc_continue.orchestrator import start_conversation
from cc_continue.storage import Storage
from cc_continue.transcript import list_sessions_for_directory
from cc_continue.tui.layout import MODAL_CSS


class _DirectoriesOnly(DirectoryTree):
    def filter_paths(self, paths):
        return [p for p in paths if p.is_dir() and not p.name.startswith(".")]


def default_browse_root() -> Path:
    dev = Path.home() / "DEV"
    return dev if dev.is_dir() else Path.home()


class NewConversationModal(ModalScreen):
    DEFAULT_CSS = MODAL_CSS.format(cls="NewConversationModal") + """
    NewConversationModal > Container {
        width: 90%;
        max-width: 150;
        height: 90%;
    }
    NewConversationModal #new-conv-columns {
        height: 1fr;
    }
    NewConversationModal #new-conv-left {
        width: 1fr;
        margin-right: 2;
    }
    NewConversationModal #new-conv-right {
        width: 1fr;
    }
    NewConversationModal #recent-dirs {
        height: 7;
        margin-bottom: 1;
    }
    NewConversationModal #dir-tree {
        height: 1fr;
        margin-bottom: 1;
    }
    NewConversationModal #resume-sessions {
        height: 8;
        margin-left: 4;
    }
    NewConversationModal #from-pr-input {
        margin-left: 4;
    }
    NewConversationModal .group-title {
        text-style: bold;
        color: green;
        margin-top: 1;
    }
    NewConversationModal Checkbox {
        border: none;
        padding: 0;
        height: 1;
        background: transparent;
    }
    NewConversationModal Checkbox > .toggle--button {
        color: $surface-lighten-2;
        background: $surface-lighten-1;
    }
    NewConversationModal Checkbox.-on > .toggle--button {
        color: black;
        background: green;
        text-style: bold;
    }
    NewConversationModal Checkbox.-on > .toggle--label {
        text-style: bold;
    }
    NewConversationModal Checkbox:disabled > .toggle--label {
        color: $text-disabled;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, storage: Storage, browse_root: Path | None = None):
        super().__init__()
        self.storage = storage
        self.browse_root = browse_root or default_browse_root()
        self.selection = DEFAULT_SELECTION
        self._sessions_for: str | None = None
        self._session_ids: list[str] = []

    def compose(self):
        right = []
        for group in GROUPS:
            if group.title:
                right.append(Static(group.title, classes="group-title"))
            for option in group.options:
                right.append(Checkbox(option.label, value=option.key in self.selection, id=f"opt-{option.key}"))
                if option.key == SESSION_RESUME:
                    right.append(OptionList(id="resume-sessions"))
                elif option.key == SESSION_FROM_PR:
                    right.append(Input(placeholder="PR number or URL", id="from-pr-input"))
        recent = [Option(Content(p), id=p) for p in self.storage.recent_project_paths()]
        box = Container(
            Horizontal(
                Vertical(
                    Static("Recent directories", classes="modal-label"),
                    OptionList(*recent, id="recent-dirs"),
                    Static("Browse", classes="modal-label"),
                    _DirectoriesOnly(str(self.browse_root), id="dir-tree"),
                    Static("Path", classes="modal-label"),
                    Input(placeholder="/path/to/project", id="launch-path"),
                    id="new-conv-left",
                ),
                VerticalScroll(*right, id="new-conv-right"),
                id="new-conv-columns",
            ),
            Static("Name (optional)", classes="modal-label"),
            Input(placeholder="defaults to the directory name", id="launch-name"),
            Static("", id="launch-error", classes="modal-error"),
            Horizontal(
                Button("Start", id="launch-start", classes="modal-submit"),
                Button("Cancel", id="launch-cancel", classes="modal-cancel"),
                classes="modal-buttons",
            ),
        )
        box.border_title = "New conversation"
        yield box

    def on_mount(self) -> None:
        self._sync_session_widgets()

    # --- directory ------------------------------------------------------

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "recent-dirs":
            self.query_one("#launch-path", Input).value = event.option.id

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.query_one("#launch-path", Input).value = str(event.path)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "launch-path":
            self._sync_session_widgets()

    def _path(self) -> str:
        return str(Path(self.query_one("#launch-path", Input).value.strip()).expanduser())

    # --- attributes -----------------------------------------------------

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        key = event.checkbox.id.removeprefix("opt-")
        if event.value == (key in self.selection):
            return  # echo of our own sync below
        self.selection = toggle(self.selection, key, event.value)
        for checkbox in self.query(Checkbox):
            wanted = checkbox.id.removeprefix("opt-") in self.selection
            if checkbox.value != wanted:
                checkbox.value = wanted
        self._sync_session_widgets()

    def _sync_session_widgets(self) -> None:
        mode = session_mode(self.selection)
        self.query_one(f"#opt-{FORK}", Checkbox).disabled = mode == SESSION_NEW
        self.query_one("#from-pr-input", Input).display = mode == SESSION_FROM_PR
        sessions = self.query_one("#resume-sessions", OptionList)
        sessions.display = mode == SESSION_RESUME
        path = self._path() if self.query_one("#launch-path", Input).value.strip() else ""
        if mode == SESSION_RESUME and path != self._sessions_for:
            self._sessions_for = path
            sessions.clear_options()
            found = list_sessions_for_directory(path) if path and Path(path).is_dir() else []
            self._session_ids = [s.session_id for s in found]
            sessions.add_options([
                Option(Content(f"{s.modified:%Y-%m-%d %H:%M} · {s.message_count} msgs · {s.first_prompt}"))
                for s in found
            ])
            if found:
                sessions.highlighted = 0

    # --- buttons --------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "launch-cancel":
            self.dismiss(None)
            return
        if event.button.id != "launch-start":
            return
        error = self.query_one("#launch-error", Static)
        if not self.query_one("#launch-path", Input).value.strip():
            error.update("Choose a directory.")
            return
        session_id = None
        if session_mode(self.selection) == SESSION_RESUME:
            highlighted = self.query_one("#resume-sessions", OptionList).highlighted
            if highlighted is not None and highlighted < len(self._session_ids):
                session_id = self._session_ids[highlighted]
        try:
            queue = start_conversation(
                self.storage,
                self._path(),
                self.selection,
                name=self.query_one("#launch-name", Input).value,
                session_id=session_id,
                pr=self.query_one("#from-pr-input", Input).value,
            )
        except ValueError as exc:
            error.update(Content(str(exc)))
            return
        self.dismiss(queue.id)

    def action_cancel(self) -> None:
        self.dismiss(None)
