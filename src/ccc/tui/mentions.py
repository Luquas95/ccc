"""@-mentions in a text box (ccc.file_mentions): typing @ opens a list of
the conversation's files above the box, narrowed as you type; ↑ ↓ pick,
Tab / Enter insert the path, Esc closes it and the @ stays a plain
character."""
from __future__ import annotations

from textual import events
from textual.widgets import OptionList, TextArea
from textual.widgets.option_list import Option

from ccc.file_mentions import INDEX, mention_at, rank
from ccc.i18n import _


class MentionPopup(OptionList):
    DEFAULT_CSS = """
    MentionPopup {
        height: auto;
        max-height: 10;
        border: round $accent;
        border-title-color: $accent;
        margin: 0;
    }
    """

    def __init__(self, owner: "FileMentions"):
        super().__init__()
        self.owner = owner
        self.can_focus = False  # the keys stay in the text box
        self.border_title = _("Files · ↑↓ Tab/Enter insert · Esc close")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()  # a click
        self.owner._insert_mention()


class FileMentions:
    """For a TextArea subclass. set_mention_source() turns it on; the
    subclass's _on_key calls mention_key() first."""

    _mention_root: str | None = None
    _mention_git = False
    # What's being typed: (row, column of the @, text after it).
    _mention: tuple[int, int, str] | None = None
    # An @ you closed the list on (Esc): not reopened until you type another.
    _mention_dismissed: tuple[int, int] | None = None
    _mention_generation = 0
    _mention_popup: MentionPopup | None = None

    def set_mention_source(self, root: str | None, use_git: bool = False) -> None:
        """The folder whose files @ offers (None: off); git only where
        Claude may run commands (gitops.claude_can_run_commands)."""
        self._mention_root, self._mention_git = root, use_git
        self._hide_mention()

    def mention_open(self) -> bool:
        return self._mention_popup is not None and self._mention_popup.display

    def close_mentions(self) -> bool:
        """Esc: close the list, leave the @ as it is. False if it wasn't open."""
        if not self.mention_open() or self._mention is None:
            return False
        row, start, _query = self._mention
        self._mention_dismissed = (row, start)
        self._hide_mention()
        return True

    def mention_key(self, event: events.Key) -> bool:
        """Keys the open list takes; True when handled."""
        if not self.mention_open():
            return False
        popup = self._mention_popup
        if event.key in ("up", "down"):
            if popup.option_count:
                popup.action_cursor_up() if event.key == "up" else popup.action_cursor_down()
        elif event.key in ("tab", "enter"):
            self._insert_mention()
        elif event.key == "escape":
            self.close_mentions()
        else:
            return False
        event.stop()
        event.prevent_default()
        return True

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._update_mention()

    def on_text_area_selection_changed(self, event: TextArea.SelectionChanged) -> None:
        self._update_mention()

    def on_blur(self, event: events.Blur) -> None:
        self._hide_mention()

    def _update_mention(self) -> None:
        if self._mention_root is None or self.read_only:
            self._hide_mention()
            return
        row, col = self.cursor_location
        found = mention_at(self.document.get_line(row)[:col])
        if found is None:
            self._mention_dismissed = None
            self._hide_mention()
            return
        start, query = found
        if self._mention_dismissed == (row, start):
            return
        if self._mention == (row, start, query) and self.mention_open():
            return
        self._mention = (row, start, query)
        self._mention_generation += 1
        generation, root, use_git = self._mention_generation, self._mention_root, self._mention_git

        def work() -> None:
            files = INDEX.files(root, use_git)
            self.app.call_from_thread(self._show_mention_hits, generation, rank(files, query))

        self.run_worker(work, thread=True, group="file-mentions", exclusive=True)

    def _show_mention_hits(self, generation: int, hits: list[str]) -> None:
        if generation != self._mention_generation or self._mention is None or not self.has_focus:
            return
        options = [Option(f"@{path}", id=path) for path in hits] or [Option(_("No matching files"), disabled=True)]
        if self._mention_popup is None:
            self._mention_popup = MentionPopup(self)
            self.parent.mount(self._mention_popup, before=self)
        popup = self._mention_popup
        popup.clear_options()
        popup.add_options(options)
        popup.highlighted = 0 if hits else None
        popup.display = True

    def _hide_mention(self) -> None:
        self._mention = None
        self._mention_generation += 1  # a list still being ranked won't show
        if self._mention_popup is not None:
            self._mention_popup.display = False

    def _insert_mention(self) -> None:
        popup = self._mention_popup
        option = popup.get_option_at_index(popup.highlighted) if popup.highlighted is not None else None
        mention = self._mention
        self._hide_mention()
        if option is None or option.id is None or mention is None:
            return
        row, start, query = mention
        self.replace(f"@{option.id} ", (row, start), (row, start + 1 + len(query)))


class MentionArea(FileMentions, TextArea):
    """A plain multi-line text box with @-mentions (the task editor)."""

    async def _on_key(self, event: events.Key) -> None:
        if self.mention_key(event):
            return
        await super()._on_key(event)
