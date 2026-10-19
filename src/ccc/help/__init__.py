"""ccc's user guide: one Markdown file per topic, shown by ? in the TUI
(tui.help.HelpScreen) and readable on GitHub, where README.md in this
folder is the table of contents. Write it for someone who has just
installed ccc."""
from __future__ import annotations

import re
from importlib.resources import files

# (slug, title) in reading order; the file is <slug>.md next to this one.
TOPICS: list[tuple[str, str]] = [
    ("getting-started", "Getting started"),
    ("dashboard", "Dashboard"),
    ("conversations", "Conversations"),
    ("new-conversation", "Starting a conversation"),
    ("tasks", "Task queue"),
    ("archive", "Archive"),
    ("limits", "Usage limits & blocked queues"),
    ("approvals", "Approving tool calls"),
    ("remote-control", "Remote control (phone)"),
    ("live-sessions", "Live sessions"),
    ("analytics", "Analytics"),
    ("settings", "Settings & notifications"),
    ("git", "Git: auto-commit & diffs"),
    ("command-line", "Command line"),
    ("troubleshooting", "Troubleshooting & how it works"),
    ("keys", "Keyboard shortcuts"),
]

# The topic ? opens on each screen (SidebarScreen.VIEW).
VIEW_TOPICS = {
    "dashboard": "dashboard",
    "conversations": "conversations",
    "archive": "archive",
    "sessions": "live-sessions",
    "analytics": "analytics",
}

_IMAGE_LINE = re.compile(r"^\s*(!\[[^\]]*\]\([^)]*\)|<img\b[^>]*>)\s*$")


def index_markdown() -> str:
    """README.md of this folder: the table of contents on GitHub."""
    lines = [
        "# ccc help",
        "",
        "The user guide of ccc. Inside ccc press `?` — the same pages, opened on",
        "the screen you're on.",
        "",
    ]
    lines += [f"{n}. [{title}]({slug}.md)" for n, (slug, title) in enumerate(TOPICS, start=1)]
    return "\n".join(lines) + "\n"


def read(slug: str) -> str:
    return files(__package__).joinpath(f"{slug}.md").read_text(encoding="utf-8")


def for_terminal(markdown: str) -> str:
    """The topic without its screenshots: they're for GitHub — in the
    terminal you're looking at the real thing."""
    return "\n".join(line for line in markdown.splitlines() if not _IMAGE_LINE.match(line)) + "\n"
