"""ccc's HTTP API, for the Android app (android/): the conversations, their
messages, sending one, approvals, a new conversation, usage limits, and a
stream of changes. Like the TUI it's just another reader / writer of the
ccc database — the daemon does the work.

It listens on 127.0.0.1 only; `tailscale serve` puts it on the tailnet
with HTTPS (see help/android-api.md). Every request needs the token
(`Authorization: Bearer …`, `ccc api token`), so another program on the
machine or a tailnet device of someone else can't use it. The database
keeps only the token's SHA-256 (it's readable by other users of the
machine), so the token is shown once, when it's made; it's checked
against the database on every request, so a new one locks the old one
out at once — open event streams too.

Standard library only (http.server), like the ccc MCP server: no web
framework to install for a handful of JSON endpoints.

GET  /api/v1/status                       daemon, counts, language
GET  /api/v1/conversations[?archived=1]   the list, with groups
GET  /api/v1/conversations/{id}           one, with its queued messages and approvals
GET  /api/v1/conversations/{id}/messages  the transcript (?after=N new ones, ?before=N older, ?limit=)
POST /api/v1/conversations/{id}/messages  {"text"}: queue a message
POST /api/v1/conversations/{id}/retry     retry / resume a blocked or paused one
POST /api/v1/conversations/{id}/seen      mark it read
DELETE /api/v1/conversations/{id}         delete it from ccc (not while it runs)
POST /api/v1/conversations/{id}/archive   {"archived": bool}
POST /api/v1/conversations/{id}/group     {"name": "…" | null}: its own group
GET  /api/v1/conversations/{id}/export    as Markdown, secrets masked
GET  /api/v1/conversations/{id}/files?q=  files of its folder for an @-mention
POST /api/v1/conversations                start one (as the New conversation window)
GET  /api/v1/groups                       grouping mode and own groups; POST groups/rename, groups/delete
GET  /api/v1/search?q=                    search every conversation
GET  /api/v1/waiting                      conversations that need you (Alt+N)
GET  /api/v1/prompt-presets               the preset prompts (Alt+1 … 9)
GET  /api/v1/launch-presets               New conversation presets and the last choice
GET  /api/v1/sessions?path=               Claude Code sessions of a folder (to resume one)
GET  /api/v1/permissions                  every approval waiting
POST /api/v1/permissions/{id}             {"decision": "allow" | "always" | "deny"}
GET  /api/v1/usage                        Claude usage limits
GET  /api/v1/projects                     recently used folders
GET  /api/v1/launch-options               what a new conversation can be started with
GET  /api/v1/events                       Server-Sent Events: "changed" with what changed
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ccc import __version__, groups, i18n, launch_options
from ccc.heartbeat import daemon_alive
from ccc.i18n import _
from ccc.models import QueueStatus
from ccc.orchestrator import send_message, start_conversation
from ccc.storage import Storage
from ccc.transcript import TranscriptEvent, find_transcript_path, parse_transcript_events

logger = logging.getLogger(__name__)

PREFIX = "/api/v1"
TOKEN_KEY = "api_token_sha256"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8737
MAX_BODY = 1024 * 1024
MESSAGES_LIMIT = 200
EVENTS_POLL_SECONDS = 1.0
EVENTS_KEEPALIVE_SECONDS = 15.0
# A conversation without a transcript yet: look for it again after this.
TRANSCRIPT_LOOKUP_SECONDS = 10.0
DECISIONS = ("allow", "always", "deny")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_token(storage: Storage) -> str:
    """A new API token; the old one stops working. Only its SHA-256 is
    kept, so this is the one time it can be shown."""
    value = secrets.token_urlsafe(32)
    storage.set_setting(TOKEN_KEY, _digest(value))
    return value


def has_token(storage: Storage) -> bool:
    return bool(storage.get_setting(TOKEN_KEY))


def token_valid(storage: Storage, given: str) -> bool:
    stored = storage.get_setting(TOKEN_KEY)
    return bool(given) and bool(stored) and hmac.compare_digest(_digest(given), stored)


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _time(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass
class _Transcript:
    path: Path | None = None
    looked_up: float = 0.0
    offset: int = 0
    events: list[TranscriptEvent] = field(default_factory=list)


class Api:
    """The endpoints without HTTP: route() takes a request and returns
    (status, JSON-able body), raising ApiError for an error."""

    def __init__(self, storage: Storage):
        self.storage = storage
        self._lock = threading.Lock()
        self._transcripts: dict[str, _Transcript] = {}
        self._routes = self._route_table()

    # --- routing -------------------------------------------------------------

    def _route_table(self) -> list[tuple[str, re.Pattern, HTTPStatus, object]]:
        """(method, path after /api/v1, status, handler(ids, query, body)); a
        number in the path is an id, passed in `ids`."""
        def ok(pattern: str, handler, method: str = "GET", status: HTTPStatus = HTTPStatus.OK):
            return method, re.compile(pattern), status, handler

        return [
            ok(r"/status", lambda ids, q, b: self.status()),
            ok(r"/conversations", lambda ids, q, b: self.conversations(archived=q.get("archived") in ("1", "true"))),
            ok(r"/conversations", lambda ids, q, b: self.create(b), "POST", HTTPStatus.CREATED),
            ok(r"/conversations/(\d+)", lambda ids, q, b: self.conversation(*ids)),
            ok(r"/conversations/(\d+)", lambda ids, q, b: self.delete(*ids), "DELETE"),
            ok(r"/conversations/(\d+)/messages", lambda ids, q, b: self.messages(
                *ids, after=_int(q, "after"), before=_int(q, "before"), limit=_int(q, "limit") or MESSAGES_LIMIT)),
            ok(r"/conversations/(\d+)/messages", lambda ids, q, b: self.send(*ids, b), "POST", HTTPStatus.CREATED),
            ok(r"/conversations/(\d+)/retry", lambda ids, q, b: self.retry(*ids), "POST"),
            ok(r"/conversations/(\d+)/seen", lambda ids, q, b: self.seen(*ids), "POST"),
            ok(r"/conversations/(\d+)/archive", lambda ids, q, b: self.archive(*ids, b), "POST"),
            ok(r"/conversations/(\d+)/group", lambda ids, q, b: self.set_group(*ids, b), "POST"),
            ok(r"/conversations/(\d+)/export", lambda ids, q, b: self.export(*ids)),
            ok(r"/conversations/(\d+)/files", lambda ids, q, b: self.files(*ids, q.get("q", ""))),
            ok(r"/groups", lambda ids, q, b: self.groups()),
            ok(r"/groups/rename", lambda ids, q, b: self.rename_group(b), "POST"),
            ok(r"/groups/delete", lambda ids, q, b: self.delete_group(b), "POST"),
            ok(r"/permissions", lambda ids, q, b: self.permissions()),
            ok(r"/permissions/(\d+)", lambda ids, q, b: self.decide(*ids, b), "POST"),
            ok(r"/search", lambda ids, q, b: self.search(q.get("q", ""))),
            ok(r"/waiting", lambda ids, q, b: self.waiting()),
            ok(r"/usage", lambda ids, q, b: self.usage()),
            ok(r"/projects", lambda ids, q, b: self.projects()),
            ok(r"/sessions", lambda ids, q, b: self.sessions(q.get("path", ""))),
            ok(r"/launch-options", lambda ids, q, b: self.launch_options()),
            ok(r"/launch-presets", lambda ids, q, b: self.launch_presets()),
            ok(r"/prompt-presets", lambda ids, q, b: self.prompt_presets()),
        ]

    def route(self, method: str, path: str, query: dict[str, str], body: dict) -> tuple[HTTPStatus, object]:
        if not path.startswith(PREFIX + "/"):
            raise ApiError(HTTPStatus.NOT_FOUND, _("Not found."))
        rest = path[len(PREFIX):].rstrip("/")
        for route_method, pattern, status, handler in self._routes:
            match = pattern.fullmatch(rest)
            if match and route_method == method:
                return status, handler([int(g) for g in match.groups()], query, body)
        raise ApiError(HTTPStatus.NOT_FOUND, _("Not found."))

    # --- endpoints ------------------------------------------------------------

    def status(self) -> dict:
        queues = [q for q in self.storage.list_queues() if not q.archived]
        return {
            "version": __version__,
            "language": i18n.language(),
            "daemon_running": daemon_alive(self.storage),
            "conversations": len(queues),
            "running": sum(q.status == QueueStatus.RUNNING for q in queues),
            "needs_approval": len(self.storage.queues_waiting_for_approval()),
        }

    def conversations(self, archived: bool = False) -> list[dict]:
        queues = [q for q in self.storage.list_queues() if q.archived == archived]
        unseen = self.storage.unseen_queue_ids()
        waiting = self.storage.queues_waiting_for_approval()
        # In list order: by group, as in the TUI.
        listed = []
        for group, members in groups.grouped(queues, self.storage.conversation_groups(), groups.mode(self.storage)):
            info = {"key": group.key, "title": group.title} if group is not None else None
            listed += [(q, info) for q in members]
        return [self._summary(q, q.id in unseen, q.id in waiting, info) for q, info in listed]

    def _summary(self, q, unseen: bool, needs_approval: bool, group: dict | None) -> dict:
        return {
            "id": q.id,
            "name": q.name,
            "path": q.project_path,
            "status": q.status.value,
            "delivery_mode": q.delivery_mode.value,
            "archived": q.archived,
            "paused": q.paused,
            "auto_continue": q.auto_continue,
            "pending": self.storage.count_pending_items(q.id),
            "needs_approval": needs_approval,
            "unseen": unseen,
            "last_error": q.last_error,
            "next_retry_at": _time(q.next_retry_at),
            "updated_at": _time(q.updated_at),
            "group": group,
        }

    def conversation(self, queue_id: int) -> dict:
        q = self._queue(queue_id)
        own = self.storage.conversation_groups().get(q.id)
        summary = self._summary(
            q, q.id in self.storage.unseen_queue_ids(), q.id in self.storage.queues_waiting_for_approval(),
            {"key": f"own:{own}", "title": own} if own else None,  # its own group (the list adds projects)
        )
        summary.update({
            "session_id": q.session_id,
            "flags": launch_options.describe_flags(q.launch_flags),
            "remote_control_url": q.remote_control_url,
            "queued": [
                {"id": item.id, "text": item.prompt_text, "not_before": _time(item.not_before)}
                for item in self.storage.list_pending_items(q.id)
            ],
            "permissions": [self._permission(r) for r in self.storage.pending_permission_requests(q.id)],
        })
        return summary

    def messages(self, queue_id: int, after: int | None = None, before: int | None = None,
                 limit: int = MESSAGES_LIMIT) -> dict:
        """Transcript events, each with its index: ?after=N the ones after
        N (polling for new ones), ?before=N the ones before (scrolling
        back); at most `limit`, the newest of them."""
        events = self._events(self._queue(queue_id).session_id)
        start = after + 1 if after is not None else 0
        end = before if before is not None else len(events)
        start, end = max(start, 0), min(end, len(events))
        start = max(start, end - max(limit, 1))
        return {
            "total": len(events),
            "messages": [
                {
                    "index": i,
                    "kind": e.kind,
                    "text": e.text,
                    "time": _time(e.timestamp),
                    "tool_use_id": e.tool_use_id,
                    "detail": e.detail,
                }
                for i, e in enumerate(events[start:end], start)
            ],
        }

    def send(self, queue_id: int, body: dict) -> dict:
        self._queue(queue_id)
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ApiError(HTTPStatus.BAD_REQUEST, _("The message is empty."))
        item = send_message(self.storage, queue_id, text)
        return {"id": item.id, "text": item.prompt_text}

    def retry(self, queue_id: int) -> dict:
        self._queue(queue_id)
        return {"retried": self.storage.retry_queue(queue_id)}

    def seen(self, queue_id: int) -> dict:
        self._queue(queue_id)
        self.storage.mark_seen(queue_id)
        return {"ok": True}

    def archive(self, queue_id: int, body: dict) -> dict:
        """{"archived": true} into the Archive, false back (as x in the TUI)."""
        self._queue(queue_id)
        archived = body.get("archived")
        if not isinstance(archived, bool):
            raise ApiError(HTTPStatus.BAD_REQUEST, _("archived must be true or false."))
        self.storage.set_queue_archived(queue_id, archived)
        return self.conversation(queue_id)

    def delete(self, queue_id: int) -> dict:
        """Out of ccc with its tasks and history; Claude Code's transcript stays."""
        queue = self._queue(queue_id)
        if queue.status == QueueStatus.RUNNING:
            raise ApiError(HTTPStatus.CONFLICT,
                           _("Claude is working on '{name}' right now — wait or pause it first.").format(name=queue.name))
        self.storage.delete_queue(queue_id)
        return {"deleted": queue_id}

    # --- groups -----------------------------------------------------------------

    def groups(self) -> dict:
        """The grouping mode and your own groups' names."""
        own = sorted(set(self.storage.conversation_groups().values()), key=str.casefold)
        return {"mode": groups.mode(self.storage), "own": own}

    def set_group(self, queue_id: int, body: dict) -> dict:
        """{"name": "…"} into that own group (made if new); null or "" out of it."""
        self._queue(queue_id)
        name = body.get("name")
        if name is not None and not isinstance(name, str):
            raise ApiError(HTTPStatus.BAD_REQUEST, _("name must be text or null."))
        self.storage.set_conversation_group(queue_id, (name or "").strip() or None)
        return self.conversation(queue_id)

    def rename_group(self, body: dict) -> dict:
        old, new = _str(body, "old").strip(), _str(body, "new").strip()
        if not old or not new:
            raise ApiError(HTTPStatus.BAD_REQUEST, _("Give the group's name and its new name."))
        groups.rename(self.storage, old, new)
        return self.groups()

    def delete_group(self, body: dict) -> dict:
        name = _str(body, "name").strip()
        if not name:
            raise ApiError(HTTPStatus.BAD_REQUEST, _("Give the group's name."))
        groups.delete(self.storage, name)
        return self.groups()

    # --- finding and sharing -------------------------------------------------------

    def search(self, text: str) -> list[dict]:
        """Every conversation's messages (archived too), newest first."""
        from ccc.search import search_conversations

        return [
            {"conversation_id": h.queue_id, "name": h.queue_name, "time": _time(h.timestamp), "kind": h.kind,
             "snippet": h.snippet}
            for h in search_conversations(self.storage, text)
        ]

    def export(self, queue_id: int) -> dict:
        """The conversation as Markdown, secrets masked — to share from the phone."""
        from ccc.search import markdown_export

        self._queue(queue_id)
        filename, text = markdown_export(self.storage, queue_id)
        return {"filename": filename, "markdown": text}

    def files(self, queue_id: int, text: str) -> list[str]:
        """Files of the conversation's folder for an @-mention, best first."""
        from ccc import gitops
        from ccc.file_mentions import INDEX, rank

        queue = self._queue(queue_id)
        return rank(INDEX.files(queue.project_path, gitops.claude_can_run_commands(queue)), text)

    def waiting(self) -> list[dict]:
        """Conversations that need you, most urgent first (Alt+N in the TUI)."""
        from ccc import attention

        return [
            {"conversation_id": w.queue_id, "name": w.name, "kind": w.kind, "label": _(attention.LABELS[w.kind])}
            for w in attention.waiting(self.storage)
        ]

    def prompt_presets(self) -> list[dict]:
        """The preset prompts (Alt+1 … Alt+9): sent at once, or put into the message box."""
        from ccc.prompt_presets import load_prompt_presets

        return [
            {"number": i, "name": p.name, "text": p.text, "send_now": p.send_now}
            for i, p in enumerate(load_prompt_presets(self.storage), 1)
        ]

    def permissions(self) -> list[dict]:
        names = {q.id: q.name for q in self.storage.list_queues()}
        return [
            dict(self._permission(r), conversation=names.get(r.queue_id))
            for queue_id in sorted(self.storage.queues_waiting_for_approval())
            for r in self.storage.pending_permission_requests(queue_id)
        ]

    @staticmethod
    def _permission(request) -> dict:
        return {
            "id": request.id,
            "conversation_id": request.queue_id,
            "tool": request.tool_name,
            "input": request.input,
            "created_at": _time(request.created_at),
        }

    def decide(self, request_id: int, body: dict) -> dict:
        decision = body.get("decision")
        if decision not in DECISIONS:
            raise ApiError(HTTPStatus.BAD_REQUEST, _("decision must be allow, always or deny."))
        request = self.storage.get_permission_request(request_id)
        if request is None:
            raise ApiError(HTTPStatus.NOT_FOUND, _("No such approval."))
        if request.status != "pending":
            raise ApiError(HTTPStatus.CONFLICT, _("This approval has already been decided."))
        if decision == "always":
            self.storage.always_allow_tool(request.queue_id, request.tool_name)
        self.storage.decide_permission_request(request.id, allow=decision != "deny")
        return {"id": request.id, "decision": decision}

    def usage(self) -> dict | None:
        from ccc.usage_api import get_pro_usage

        usage = get_pro_usage()
        if usage is None:
            return None

        def window(w) -> dict | None:
            return {"percent": w.utilization_pct, "resets_at": _time(w.resets_at)} if w else None

        return {
            "five_hour": window(usage.five_hour),
            "seven_day": window(usage.seven_day),
            "per_model": [
                {"model": m.model, "percent": m.utilization_pct, "resets_at": _time(m.resets_at)}
                for m in usage.per_model
            ],
        }

    def projects(self) -> list[str]:
        return self.storage.recent_project_paths()

    def sessions(self, path: str) -> list[dict]:
        """Claude Code sessions recorded in a folder, newest first (to resume one)."""
        from ccc.transcript import list_sessions_for_directory

        folder = os.path.expanduser(path.strip())
        if not folder or not os.path.isdir(folder):
            return []
        return [
            {"session_id": s.session_id, "modified": _time(s.modified), "first_prompt": s.first_prompt,
             "messages": s.message_count}
            for s in list_sessions_for_directory(folder)
        ]

    def launch_presets(self) -> dict:
        """The New conversation window's presets and the last choice."""
        from ccc import presets

        def choice(c) -> dict | None:
            if c is None:
                return None
            return {"options": sorted(c.selection), "auto_continue": c.auto_continue,
                    "remote_control": c.remote_control}

        return {
            "last": choice(presets.load_last(self.storage)),
            "presets": [dict(choice(c), name=name) for name, c in presets.list_presets(self.storage).items()],
        }

    def launch_options(self) -> dict:
        return {
            "groups": [
                {
                    "key": group.key,
                    "title": _(group.title) if group.title else "",
                    "exclusive": group.exclusive,
                    "required": group.required,
                    "options": [{"key": o.key, "label": _(o.label)} for o in group.options],
                }
                for group in launch_options.GROUPS
            ],
            "default": sorted(launch_options.DEFAULT_SELECTION),
        }

    def create(self, body: dict) -> dict:
        """A new conversation, as the New conversation window starts it.
        Options missing from a required group (session, permissions) are
        the defaults."""
        path = body.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ApiError(HTTPStatus.BAD_REQUEST, _("Choose a directory."))
        selection = self._selection(body.get("options"))
        try:
            queue = start_conversation(
                self.storage, os.path.expanduser(path.strip()), selection,
                name=_str(body, "name"), session_id=_str(body, "session_id") or None, pr=_str(body, "pr"),
                auto_continue=bool(body.get("auto_continue", True)),
                remote_control=bool(body.get("remote_control", False)),
                interactive=bool(body.get("interactive", True)),
                worktree=bool(body.get("worktree", False)),
            )
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
        from ccc.presets import LaunchChoice, save_last

        save_last(self.storage, LaunchChoice(selection, bool(body.get("auto_continue", True)),
                                             bool(body.get("remote_control", False))))
        prompt = body.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            send_message(self.storage, queue.id, prompt)
        return self.conversation(queue.id)

    @staticmethod
    def _selection(options) -> frozenset[str]:
        if options is None:
            return launch_options.DEFAULT_SELECTION
        if not isinstance(options, list) or not all(isinstance(o, str) for o in options):
            raise ApiError(HTTPStatus.BAD_REQUEST, _("options must be a list of option keys."))
        selection = set(options)
        for group in launch_options.GROUPS:
            chosen = selection & {o.key for o in group.options}
            if group.exclusive and len(chosen) > 1:
                raise ApiError(HTTPStatus.BAD_REQUEST,
                               _("Choose one of: {options}.").format(options=", ".join(sorted(chosen))))
            if group.required and not chosen:
                selection |= {o.key for o in group.options} & launch_options.DEFAULT_SELECTION
        known = {o.key for g in launch_options.GROUPS for o in g.options}
        unknown = selection - known
        if unknown:
            raise ApiError(HTTPStatus.BAD_REQUEST,
                           _("Unknown options: {options}.").format(options=", ".join(sorted(unknown))))
        return frozenset(selection)

    # --- changes (the events stream) -----------------------------------------

    def snapshot(self) -> dict[int, tuple]:
        """What the app shows of each conversation; a difference between
        two snapshots is a change to tell it about."""
        unseen = self.storage.unseen_queue_ids()
        waiting = self.storage.queues_waiting_for_approval()
        own = self.storage.conversation_groups()
        result = {}
        for q in self.storage.list_queues():
            transcript = self._transcript(q.session_id)
            try:
                size = transcript.path.stat().st_size if transcript.path else 0
            except OSError:
                size = 0
            result[q.id] = (
                q.name, q.status.value, q.archived, q.paused, q.last_error, own.get(q.id),
                self.storage.count_pending_items(q.id), q.id in waiting, q.id in unseen, size,
            )
        return result

    @staticmethod
    def changes(before: dict[int, tuple], after: dict[int, tuple]) -> dict | None:
        changed = sorted(i for i in after if before.get(i) != after[i])
        removed = sorted(set(before) - set(after))
        if not changed and not removed:
            return None
        return {"conversations": changed, "removed": removed}

    # --- helpers --------------------------------------------------------------

    def _queue(self, queue_id: int):
        queue = self.storage.find_queue(queue_id)
        if queue is None:
            raise ApiError(HTTPStatus.NOT_FOUND, _("No such conversation."))
        return queue

    def _transcript(self, session_id: str) -> _Transcript:
        with self._lock:
            cached = self._transcripts.setdefault(session_id, _Transcript())
            now = time.monotonic()
            if cached.path is None and now - cached.looked_up >= TRANSCRIPT_LOOKUP_SECONDS:
                cached.looked_up = now
                cached.path = find_transcript_path(session_id)
            return cached

    def _events(self, session_id: str) -> list[TranscriptEvent]:
        cached = self._transcript(session_id)
        with self._lock:
            if cached.path is None:
                return []
            try:
                events, cached.offset = parse_transcript_events(cached.path, since_byte_offset=cached.offset)
            except OSError:
                return list(cached.events)
            cached.events.extend(events)
            return list(cached.events)


def _int(query: dict[str, str], key: str) -> int | None:
    raw = query.get(key)
    if raw is None:
        return None
    if not re.fullmatch(r"-?\d+", raw):
        raise ApiError(HTTPStatus.BAD_REQUEST, _("{name} must be a number.").format(name=key))
    return int(raw)


def _str(body: dict, key: str) -> str:
    value = body.get(key)
    return value if isinstance(value, str) else ""


class _Handler(BaseHTTPRequestHandler):
    api: Api
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_DELETE(self) -> None:
        self._handle("DELETE")

    def _handle(self, method: str) -> None:
        url = urlsplit(self.path)
        query = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            i18n.load(self.api.storage)  # follows the language set in the TUI
            if not self._authorized():
                raise ApiError(HTTPStatus.UNAUTHORIZED, _("Missing or wrong API token."))
            if method == "GET" and url.path == PREFIX + "/events":
                self._events()
                return
            body = self._body() if method == "POST" else {}
            status, result = self.api.route(method, url.path, query, body)
        except ApiError as exc:
            status, result = exc.status, {"error": exc.message}
        except Exception:
            logger.exception("API request %s %s failed", method, url.path)
            status, result = HTTPStatus.INTERNAL_SERVER_ERROR, {"error": _("Something went wrong in ccc.")}
        self._send(status, result)

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        self._token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
        return token_valid(self.api.storage, self._token)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            raise ApiError(HTTPStatus.BAD_REQUEST, _("Bad request body."))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, _("The body isn't valid JSON.")) from exc
        if not isinstance(body, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, _("The body must be a JSON object."))
        return body

    def _send(self, status: HTTPStatus, result: object) -> None:
        data = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _events(self) -> None:
        """Server-Sent Events: "changed" whenever a conversation changes
        (status, queued messages, approvals, a new transcript line);
        the app then fetches what it shows."""
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.close_connection = True
        before = self.api.snapshot()
        quiet = 0.0
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                time.sleep(EVENTS_POLL_SECONDS)
                if not token_valid(self.api.storage, self._token):
                    return  # a new token was made: this one is out
                after = self.api.snapshot()
                change = self.api.changes(before, after)
                before = after
                if change is not None:
                    self.wfile.write(f"event: changed\ndata: {json.dumps(change)}\n\n".encode())
                    quiet = 0.0
                else:
                    quiet += EVENTS_POLL_SECONDS
                    if quiet < EVENTS_KEEPALIVE_SECONDS:
                        continue
                    self.wfile.write(b": keepalive\n\n")
                    quiet = 0.0
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the app went away

    def log_message(self, format: str, *args) -> None:
        logger.debug("%s " + format, self.address_string(), *args)


def make_server(storage: Storage, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    handler = type("Handler", (_Handler,), {"api": Api(storage)})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def serve(db_path: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    storage = Storage(db_path)
    i18n.load(storage)
    server = make_server(storage, host, port)
    if not has_token(storage):
        logger.warning("no API token yet — every request is refused until you make one: ccc api token")
    logger.info("ccc API on http://%s:%s%s", host, port, PREFIX)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
