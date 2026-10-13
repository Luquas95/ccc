import json
import os
import subprocess
import sys
import threading
import time

from ccc.permission_mcp import decide, handle
from ccc.storage import Storage


def _storage(tmp_path):
    storage = Storage(tmp_path / "h.db")
    return storage, storage.create_queue("conv", "/tmp/c", "s1")


def test_always_allowed_tool_is_approved_without_asking(tmp_path):
    storage, q = _storage(tmp_path)
    storage.always_allow_tool(q.id, "Bash")
    assert decide(storage, q.id, "Bash", {"command": "ls"}) == {"behavior": "allow", "updatedInput": {"command": "ls"}}
    assert storage.pending_permission_requests(q.id) == []


def test_waits_until_user_decides(tmp_path):
    storage, q = _storage(tmp_path)
    notes = []

    class N:
        def send_now(self, text):
            notes.append(text)

    def approve_later():
        while not storage.pending_permission_requests(q.id):
            time.sleep(0.01)
        storage.decide_permission_request(storage.pending_permission_requests(q.id)[0].id, allow=False)

    threading.Thread(target=approve_later).start()
    result = decide(storage, q.id, "Write", {"file_path": "/x"}, poll=0.01, notifier=N())
    assert result["behavior"] == "deny" and "ccc" in result["message"]
    assert notes and "conv" in notes[0] and "Write" in notes[0]


def test_deleted_conversation_denies(tmp_path):
    storage, q = _storage(tmp_path)

    def delete_later():
        while not storage.pending_permission_requests(q.id):
            time.sleep(0.01)
        storage.delete_queue(q.id)

    threading.Thread(target=delete_later).start()
    assert decide(storage, q.id, "Bash", {}, poll=0.01)["behavior"] == "deny"


def test_jsonrpc_handshake_and_tool_list(tmp_path):
    storage, q = _storage(tmp_path)
    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                   "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}}},
                  storage, q.id)
    assert init["result"]["protocolVersion"] == "2025-06-18" and "tools" in init["result"]["capabilities"]
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, storage, q.id) is None
    tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, storage, q.id)["result"]["tools"]
    assert [t["name"] for t in tools] == ["approve"]
    assert handle({"jsonrpc": "2.0", "id": 3, "method": "nope"}, storage, q.id)["error"]["code"] == -32601


def test_server_process_end_to_end(tmp_path):
    storage, q = _storage(tmp_path)
    storage.always_allow_tool(q.id, "Read")
    env = {**os.environ, "CCC_DB": str(tmp_path / "h.db"), "CCC_QUEUE_ID": str(q.id)}
    proc = subprocess.Popen([sys.executable, "-m", "ccc.permission_mcp"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, env=env)
    try:
        def call(msg):
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        reply = call({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                      "params": {"name": "approve", "arguments": {"tool_name": "Read", "input": {"file_path": "/a"}}}})
        decision = json.loads(reply["result"]["content"][0]["text"])
        assert decision == {"behavior": "allow", "updatedInput": {"file_path": "/a"}}
    finally:
        proc.kill()
