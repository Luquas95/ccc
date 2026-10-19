"""The help window (? on any screen): the user guide in ccc.help plus
every keyboard shortcut."""
from __future__ import annotations

from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, OptionList
from textual.widgets.option_list import Option

from ccc import help as help_topics
from ccc.i18n import N_, _
from ccc.tui.layout import MODAL_CSS

# (section, [(binding key, description)]) — keys as Textual names them;
# tests check every screen's bindings are listed here.
KEY_HELP: list[tuple[str, list[tuple[str, str]]]] = [
    (N_("Everywhere"), [
        ("d", N_("Dashboard")),
        ("c", N_("Conversations")),
        ("h", N_("Archive (archived conversations)")),
        ("s", N_("Live sessions")),
        ("v", N_("Analytics")),
        ("n", N_("New conversation")),
        ("question_mark", N_("This help")),
        ("ctrl+p", N_("Settings (language, theme, Telegram, queues, presets, backup)")),
        ("ctrl+q", N_("Close ccc (it keeps running; `ccc` opens it again)")),
        ("escape", N_("Back / close")),
    ]),
    (N_("Dashboard"), [
        ("enter", N_("Open the queue detail")),
        ("q", N_("Close ccc (same as Ctrl+Q)")),
    ]),
    (N_("Live sessions"), [
        ("enter", N_("Send the selected session a prompt")),
        ("r", N_("Reload the session list")),
        ("a", N_("Add a prompt to a project's queue")),
    ]),
    (N_("Conversations"), [
        ("enter", N_("Open the conversation's Claude Code CLI (in the list) / send the message (in the box)")),
        ("r", N_("Blocked: run the failed task again / resume one paused at a limit")),
        ("t", N_("Tasks editor (queue, schedule, pause, auto-continue)")),
        ("p", N_("Approve a tool call Claude is waiting on")),
        ("x", N_("Archive (moves it to Archive, h)")),
        ("alt+0", N_("Switch between ccc and Claude Code (while it's open beside ccc)")),
        ("ctrl+right_square_bracket", N_("Close Claude Code beside ccc (it keeps running; Enter in the list opens it)")),
        ("slash", N_("Search all conversations")),
        ("e", N_("Export the conversation as Markdown")),
        ("ctrl+j", N_("New line in the message box (Shift+Enter where supported)")),
        ("alt+1", N_("Preset prompt 1–9 (⏎ sends it, ✎ puts it into the message box; set in Settings)")),
        ("alt+2", N_("Preset prompt 2")),
        ("alt+3", N_("Preset prompt 3")),
        ("alt+4", N_("Preset prompt 4")),
        ("alt+5", N_("Preset prompt 5")),
        ("alt+6", N_("Preset prompt 6")),
        ("alt+7", N_("Preset prompt 7")),
        ("alt+8", N_("Preset prompt 8")),
        ("alt+9", N_("Preset prompt 9")),
    ]),
    (N_("Archive"), [
        ("x", N_("Restore the conversation")),
        ("enter", N_("Restore it and open it in Conversations")),
        ("delete", N_("Delete the conversation from ccc (asks first; Claude Code's transcript stays)")),
        ("slash", N_("Search all conversations")),
        ("e", N_("Export the conversation as Markdown")),
    ]),
    (N_("Tasks editor (t)"), [
        ("a", N_("Add a task")),
        ("e", N_("Edit the task (also Enter)")),
        ("delete", N_("Remove the task")),
        ("ctrl+up", N_("Move up")),
        ("ctrl+down", N_("Move down")),
        ("p", N_("Pause / resume the queue")),
        ("o", N_("Toggle auto-continue")),
        ("ctrl+s", N_("Save in the task editor")),
    ]),
    (N_("Approval window (p)"), [
        ("y", N_("Allow")),
        ("a", N_("Always allow this tool in this conversation")),
        ("n", N_("Deny")),
    ]),
    (N_("Analytics"), [
        ("left", N_("Previous calendar month")),
        ("right", N_("Next calendar month")),
    ]),
    (N_("Queue detail"), [
        ("enter", N_("Show the run's commit diff")),
        ("a", N_("Add a prompt (this queue's path prefilled)")),
        ("r", N_("Blocked: run the failed task again / resume one paused at a limit")),
    ]),
    (N_("Preset prompt editor (Settings → Add / Edit)"), [
        ("ctrl+s", N_("Save")),
        ("escape", N_("Cancel")),
    ]),
    (N_("Settings (Ctrl+P)"), [
        ("ctrl+s", N_("Save")),
        ("escape", N_("Cancel (the theme goes back too)")),
    ]),
]

_PRETTY = {
    "question_mark": "?", "escape": "Esc", "enter": "Enter", "slash": "/", "delete": "Del",
    "ctrl+d": "Ctrl+D", "ctrl+p": "Ctrl+P", "ctrl+t": "Ctrl+T", "ctrl+q": "Ctrl+Q", "left": "←", "right": "→",
    **{f"alt+{n}": f"Alt+{n}" for n in range(0, 10)}, "ctrl+right_square_bracket": "Ctrl+]", "ctrl+j": "Ctrl+J", "ctrl+s": "Ctrl+S", "ctrl+up": "Ctrl+↑", "ctrl+down": "Ctrl+↓",
}


def pretty_key(key: str) -> str:
    return _PRETTY.get(key, key)


def keys_markdown() -> str:
    """KEY_HELP as the "Keyboard shortcuts" help topic (help/keys.md is
    this, kept in sync by a test)."""
    lines = [
        "# " + _("Keyboard shortcuts"),
        "",
        _("Keys without Ctrl or Alt don't work while you're typing in a text field;\n"
          "Ctrl and Alt keys work everywhere. The bar at the bottom of the window\n"
          "lists the keys of the screen you're on — click one to press it."),
    ]
    for section, entries in KEY_HELP:
        lines += ["", f"## {_(section)}", "", "| " + _("Key") + " | |", "|---|---|"]
        lines += [f"| `{pretty_key(key)}` | {_(description).replace('|', '\\|')} |" for key, description in entries]
    return "\n".join(lines) + "\n"


class HelpScreen(ModalScreen):
    """The user guide (ccc.help): topics on the left, the selected one on
    the right. Opens on the topic of the screen you came from."""

    DEFAULT_CSS = MODAL_CSS.format(cls="HelpScreen") + """
    HelpScreen > Container {
        width: 95%;
        max-width: 140;
        height: 95%;
        padding: 0 1;
    }
    HelpScreen Horizontal {
        height: 1fr;
    }
    HelpScreen #help-topics {
        width: 34;
        height: 1fr;
        border: none;
        padding: 0;
    }
    HelpScreen #help-scroll {
        width: 1fr;
        height: 1fr;
        padding: 0 1 0 2;
    }
    HelpScreen #help-text {
        margin: 0;
    }
    """

    BINDINGS = [("escape", "close", _("Close")), ("question_mark", "close", _("Close"))]

    def __init__(self, topic: str = "getting-started"):
        super().__init__()
        slugs = [slug for slug, _title in help_topics.TOPICS]
        self.topic = topic if topic in slugs else slugs[0]

    def compose(self):
        topics = OptionList(*[Option(_(title), id=slug) for slug, title in help_topics.TOPICS], id="help-topics")
        box = Container(
            Horizontal(
                topics,
                VerticalScroll(Markdown(id="help-text", open_links=False), id="help-scroll"),
            )
        )
        box.border_title = _("Help  ·  ↑↓ topic  ·  Tab text / topics  ·  Esc close")
        yield box

    def on_mount(self) -> None:
        topics = self.query_one("#help-topics", OptionList)
        topics.highlighted = topics.get_option_index(self.topic)
        topics.focus()
        self.show_topic(self.topic)

    def show_topic(self, slug: str) -> None:
        self.topic = slug
        text = keys_markdown() if slug == "keys" else help_topics.for_terminal(help_topics.read(slug))
        self.query_one("#help-text", Markdown).update(text)
        self.query_one("#help-scroll", VerticalScroll).scroll_home(animate=False)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id and event.option.id != self.topic:
            self.show_topic(event.option.id)

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        # Links between topics are "tasks.md"; anything else goes to the browser.
        slug = event.href.split("#")[0].removesuffix(".md")
        topics = self.query_one("#help-topics", OptionList)
        if event.href.split("#")[0].endswith(".md") and slug in dict(help_topics.TOPICS):
            topics.highlighted = topics.get_option_index(slug)
        elif event.href.startswith(("http://", "https://")):
            self.app.open_url(event.href)

    def action_close(self) -> None:
        self.dismiss()
