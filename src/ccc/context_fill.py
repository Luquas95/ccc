"""How full a conversation's context window is.

Claude Code writes every model reply with its token usage into the
session's transcript. The prompt of the last reply — `input_tokens +
cache_read_input_tokens + cache_creation_input_tokens` — is what the
conversation carries into the next turn, the same number Claude Code's
`/context` and status line work with. Divided by the model's window it
gives the fill in %, so you can `/compact` or start a new conversation
before Claude Code compacts on its own and drops details.

The window isn't in the transcript (an `opus[1m]` session records plain
`claude-opus-…`), so it's taken from what is known, never guessed:
`[1m]` in the conversation's `--model`, a prompt that already went past
200k (only a 1M window holds that), the window set in Settings, else
200k for a Claude model. A model ccc doesn't know gets tokens only."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

from ccc import transcript
from ccc.i18n import _

WINDOW_KEY = "context_window"  # "" = auto, else tokens
WARN_KEY = "context_warn_percent"
DANGER_KEY = "context_danger_percent"
NOTIFY_KEY = "context_notify"  # "" = on, "off"
ALERTED_KEY = "context_alerted"  # queue ids already notified, comma separated

STANDARD_WINDOW = 200_000
LARGE_WINDOW = 1_000_000
WINDOW_CHOICES = (STANDARD_WINDOW, LARGE_WINDOW)
DEFAULT_WARN = 80
DEFAULT_DANGER = 90
THRESHOLD_CHOICES = (50, 60, 70, 75, 80, 85, 90, 95)
SKIPPED_MODELS = {"<synthetic>"}  # Claude Code's own placeholder replies, no API call
# Cheap pre-filter: most transcript lines aren't replies, and transcripts
# can be many MB.
_REPLY_MARK = b'"assistant"'


@dataclass(frozen=True)
class ContextFill:
    tokens: int
    window: int | None  # None: the model is unknown, only tokens are shown

    @property
    def percent(self) -> int | None:
        return None if not self.window else round(self.tokens * 100 / self.window)


def short_tokens(n: int) -> str:
    """124k, 1M, 1.2M."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        return f"{round(n / 1000)}k"
    return str(n)


def thresholds(storage) -> tuple[int, int]:
    """Warning (yellow) and alarm (red) percentages from Settings."""
    def read(key: str, default: int) -> int:
        try:
            return int(storage.get_setting(key) or default)
        except ValueError:
            return default

    return read(WARN_KEY, DEFAULT_WARN), read(DANGER_KEY, DEFAULT_DANGER)


def window_setting(storage) -> int | None:
    try:
        return int(storage.get_setting(WINDOW_KEY) or 0) or None
    except ValueError:
        return None


def level(fill: ContextFill | None, warn: int, danger: int) -> str:
    """"danger", "warn" or "" — the colour of the fill."""
    percent = fill.percent if fill is not None else None
    if percent is None:
        return ""
    if percent >= danger:
        return "danger"
    return "warn" if percent >= warn else ""


LEVEL_STYLES = {"danger": "bold red", "warn": "yellow", "": "dim"}


def flag_model(flags: list[str] | None) -> str | None:
    """The `--model` a conversation is started with, if any."""
    flags = flags or []
    for n, flag in enumerate(flags):
        if flag == "--model" and n + 1 < len(flags):
            return flags[n + 1]
        if flag.startswith("--model="):
            return flag.split("=", 1)[1]
    return None


def window_for(model: str | None, flags: list[str] | None, peak: int, setting: int | None) -> int | None:
    """The window of a conversation's model; None when it can't be known."""
    flagged = flag_model(flags)
    if flagged and "[1m]" in flagged.lower():
        return LARGE_WINDOW
    if peak > STANDARD_WINDOW:
        return LARGE_WINDOW
    if setting:
        return setting
    if model and model.startswith("claude-"):
        return STANDARD_WINDOW
    return None


@dataclass
class _FileState:
    offset: int = 0
    tokens: int | None = None  # prompt of the last reply
    model: str | None = None
    peak: int = 0  # biggest prompt so far


def _reply(data: dict) -> tuple[int, str] | None:
    """Prompt tokens and model of a main-conversation reply."""
    if data.get("type") != "assistant" or data.get("isSidechain"):
        return None
    message = data.get("message")
    if not isinstance(message, dict):
        return None
    usage, model = message.get("usage"), message.get("model")
    if not isinstance(usage, dict) or not model or model in SKIPPED_MODELS:
        return None
    tokens = sum(v for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
                 if isinstance(v := usage.get(k), int))
    return (tokens, str(model)) if tokens else None


def _read(path: Path, state: _FileState) -> None:
    """New complete lines from state.offset; a trailing incomplete line
    (the file is being written) is left for the next call."""
    with path.open("rb") as fh:
        fh.seek(state.offset)
        data = fh.read()
    end = data.rfind(b"\n") + 1
    for raw in data[:end].splitlines():
        if _REPLY_MARK not in raw:
            continue
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        reply = _reply(line) if isinstance(line, dict) else None
        if reply is not None:
            state.tokens, state.model = reply
            state.peak = max(state.peak, state.tokens)
    state.offset += end


@dataclass
class ContextTracker:
    """Keeps read offsets per transcript between calls, so only new lines
    are read: the first look at a long transcript reads it once, then each
    refresh only what was appended (a cache by the file's size)."""

    projects_root: Path | None = None
    _files: dict[Path, _FileState] = field(default_factory=dict)
    _paths: dict[str, Path] = field(default_factory=dict)
    # Refreshes run in threads and may overlap: one reads at a time.
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _path(self, session_id: str) -> Path | None:
        path = self._paths.get(session_id)
        if path is None or not path.exists():
            root = self.projects_root or transcript.PROJECTS_ROOT
            matches = list(root.glob(f"*/{session_id}.jsonl"))
            path = matches[0] if matches else None
            if path is not None:
                self._paths[session_id] = path
        return path

    def fill(self, queue, window_setting: int | None = None) -> ContextFill | None:
        """The context fill of a conversation; None before its first reply."""
        path = self._path(queue.session_id)
        if path is None:
            return None
        state = self._files.setdefault(path, _FileState())
        try:
            if path.stat().st_size < state.offset:  # file replaced / truncated
                state = self._files[path] = _FileState()
            _read(path, state)
        except OSError:
            return None
        if state.tokens is None:
            return None
        return ContextFill(state.tokens, window_for(state.model, queue.launch_flags, state.peak, window_setting))

    def fills(self, storage, queues) -> dict[int, ContextFill]:
        setting = window_setting(storage)
        result = {}
        with self._lock:
            for queue in queues:
                fill = self.fill(queue, setting)
                if fill is not None:
                    result[queue.id] = fill
        return result


def list_text(fill: ContextFill) -> str:
    """Short form for the list of conversations: 62% · 124k/200k (or 124k)."""
    if fill.percent is None:
        return short_tokens(fill.tokens)
    return f"{fill.percent}% · {short_tokens(fill.tokens)}/{short_tokens(fill.window)}"


def header_text(fill: ContextFill) -> str:
    """context 62 % · 124k / 200k (or context 124k tokens)."""
    if fill.percent is None:
        return _("context {tokens} tokens (window unknown)").format(tokens=short_tokens(fill.tokens))
    return _("context {percent} % · {tokens} / {window}").format(
        percent=fill.percent, tokens=short_tokens(fill.tokens), window=short_tokens(fill.window))


def _alerted(storage) -> set[int]:
    raw = storage.get_setting(ALERTED_KEY) or ""
    return {int(x) for x in raw.split(",") if x.strip().isdigit()}


def alerts(storage, fills: dict[int, ContextFill]) -> list[int]:
    """Conversations that just reached the warning threshold: each once,
    again only after it dropped below (/compact, /clear). Returns their
    ids; what was alerted is kept in the settings."""
    warn, _danger = thresholds(storage)
    before = _alerted(storage)
    alerted = set(before)
    new = []
    for queue_id, fill in fills.items():
        percent = fill.percent
        if percent is None:
            continue
        if percent >= warn and queue_id not in alerted:
            new.append(queue_id)
            alerted.add(queue_id)
        elif percent < warn:
            alerted.discard(queue_id)
    if alerted != before:
        storage.set_setting(ALERTED_KEY, ",".join(str(x) for x in sorted(alerted)))
    return new


def notify_enabled(storage) -> bool:
    return (storage.get_setting(NOTIFY_KEY) or "") != "off"
