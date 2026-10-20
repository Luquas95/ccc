"""ccc's MCP server (stdio, JSON-RPC 2.0, no SDK dependency), attached
to every conversation the daemon runs (orchestrator.ccc_mcp_flags). Tools:

- `approve`, behind `claude -p --permission-prompt-tool mcp__ccc__approve`
  in headless conversations not started with "Skip all permission
  checks": when Claude wants a tool that needs approval, the request is
  stored in the ccc database and the call blocks — without a time limit —
  until the user allows or denies it in the TUI. The answer is the JSON
  Claude Code expects: {"behavior": "allow", "updatedInput": …} or
  {"behavior": "deny", "message": …}.
- `ask_conversation`: put a question to another ccc conversation
  (ccc.asks). It doesn't wait — the answer comes later as a message.

Run as `python -m ccc.permission_mcp` with CCC_DB and CCC_QUEUE_ID set.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

from ccc.i18n import _
from ccc.notify import Notifier
from ccc.storage import Storage

SERVER_NAME = "ccc"
TOOL_NAME = "approve"
ASK_TOOL = "ask_conversation"
FALLBACK_PROTOCOL = "2024-11-05"
POLL_SECONDS = 1.0
DENY_MESSAGE = "Denied by the user in ccc."

_TOOL = {
    "name": TOOL_NAME,
    "description": "Asks the ccc user to approve a tool call (used as Claude Code's permission prompt tool).",
    "inputSchema": {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string"},
            "input": {"type": "object"},
            "tool_use_id": {"type": "string"},
        },
        "required": ["tool_name", "input"],
    },
}


def _ask_tool(storage: Storage, queue_id: int) -> dict:
    """The ask tool, its description listing the conversations there are now."""
    others = [q for q in storage.list_queues() if not q.archived and q.id != queue_id and q.routine_id is None]
    names = "; ".join(q.name for q in others[:30]) or "none"
    return {
        "name": ASK_TOOL,
        "description": ("Ask another Claude Code conversation that ccc runs (e.g. the one working on the API, or a "
                        "reviewer) a question. It doesn't wait: the question goes into that conversation's queue and "
                        "its answer comes back to you later as a message in this conversation — carry on meanwhile. "
                        f"Conversations: {names}."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "conversation": {"type": "string", "description": "its name (or id)"},
                "question": {"type": "string"},
            },
            "required": ["conversation", "question"],
        },
    }


def ask_conversation(storage: Storage, queue_id: int, args: dict) -> tuple[str, bool]:
    """(the tool's answer, is it an error)."""
    from ccc import asks

    try:
        found = asks.ask(storage, queue_id, str(args.get("conversation", "")), str(args.get("question", "")),
                         by_agent=True)
    except ValueError as error:
        return str(error), True
    target = storage.get_queue(found.to_queue_id)
    return (f"Asked “{target.name}” (question #{found.id}). Its answer will come to you as a later message in this "
            "conversation; carry on with other work meanwhile — don't wait or poll for it."), False


def _preview(tool_input: dict) -> str:
    text = json.dumps(tool_input, ensure_ascii=False)
    return text if len(text) <= 200 else text[:200] + "…"


def decide(storage: Storage, queue_id: int, tool_name: str, tool_input: dict,
           poll: float = POLL_SECONDS, notifier=None) -> dict:
    if storage.is_tool_always_allowed(queue_id, tool_name):
        return {"behavior": "allow", "updatedInput": tool_input}
    request = storage.create_permission_request(queue_id, tool_name, tool_input)
    if notifier is not None:
        queue = storage.find_queue(queue_id)
        name = queue.name if queue else _("queue {id}").format(id=queue_id)
        notifier.send_now(
            _("✋ {name} needs you: Claude wants to use {tool} — {preview}\n"
              "Open the conversation in ccc and press p.").format(name=name, tool=tool_name, preview=_preview(tool_input))
        )
    while True:
        current = storage.get_permission_request(request.id)
        if current is None:  # conversation deleted meanwhile
            return {"behavior": "deny", "message": "The conversation was deleted in ccc."}
        if current.status == "allowed":
            return {"behavior": "allow", "updatedInput": tool_input}
        if current.status == "denied":
            return {"behavior": "deny", "message": DENY_MESSAGE}
        time.sleep(poll)


def handle(message: dict, storage: Storage, queue_id: int, notifier=None) -> dict | None:
    """One JSON-RPC message in, the response out (None for notifications)."""
    method = message.get("method")
    msg_id = message.get("id")
    if msg_id is None:
        return None  # notification, e.g. notifications/initialized

    def result(value):
        return {"jsonrpc": "2.0", "id": msg_id, "result": value}

    if method == "initialize":
        version = (message.get("params") or {}).get("protocolVersion") or FALLBACK_PROTOCOL
        return result({
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": "1"},
        })
    if method == "ping":
        return result({})
    if method == "tools/list":
        return result({"tools": [_TOOL, _ask_tool(storage, queue_id)]})
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") == ASK_TOOL:
            text, is_error = ask_conversation(storage, queue_id, params.get("arguments") or {})
            return result({"content": [{"type": "text", "text": text}], "isError": is_error})
        if params.get("name") != TOOL_NAME:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": "unknown tool"}}
        args = params.get("arguments") or {}
        tool_input = args.get("input") if isinstance(args.get("input"), dict) else {}
        decision = decide(storage, queue_id, str(args.get("tool_name", "?")), tool_input, notifier=notifier)
        return result({"content": [{"type": "text", "text": json.dumps(decision, ensure_ascii=False)}]})
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"unknown method {method}"}}


def main() -> None:
    storage = Storage(os.environ["CCC_DB"])
    queue_id = int(os.environ["CCC_QUEUE_ID"])
    notifier = Notifier(storage)
    write_lock = threading.Lock()

    def respond(message: dict) -> None:
        try:
            response = handle(message, storage, queue_id, notifier)
        except Exception as exc:  # never kill the server over one request
            response = {"jsonrpc": "2.0", "id": message.get("id"),
                        "error": {"code": -32603, "message": type(exc).__name__}}
        if response is not None:
            with write_lock:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("method") == "tools/call":
            # Blocks until the user decides — keep answering pings meanwhile.
            threading.Thread(target=respond, args=(message,), daemon=True).start()
        else:
            respond(message)


if __name__ == "__main__":
    main()
