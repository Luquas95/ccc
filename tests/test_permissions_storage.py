from ccc.storage import Storage


def test_request_lifecycle_and_always_allow(tmp_path):
    storage = Storage(tmp_path / "h.db")
    q = storage.create_queue("a", "/tmp/a", "s1")
    req = storage.create_permission_request(q.id, "Bash", {"command": "ls"})
    assert req.status == "pending" and req.input == {"command": "ls"}
    assert [r.id for r in storage.pending_permission_requests(q.id)] == [req.id]
    assert storage.queues_waiting_for_approval() == {q.id}
    storage.decide_permission_request(req.id, allow=True)
    assert storage.get_permission_request(req.id).status == "allowed"
    assert storage.pending_permission_requests(q.id) == []
    assert storage.queues_waiting_for_approval() == set()

    assert storage.is_tool_always_allowed(q.id, "Bash") is False
    storage.always_allow_tool(q.id, "Bash")
    storage.always_allow_tool(q.id, "Bash")  # idempotent
    assert storage.is_tool_always_allowed(q.id, "Bash") is True
    other = storage.create_queue("b", "/tmp/b", "s2")
    assert storage.is_tool_always_allowed(other.id, "Bash") is False


def test_deny_and_delete_queue_cleans_up(tmp_path):
    storage = Storage(tmp_path / "h.db")
    q = storage.create_queue("a", "/tmp/a", "s1")
    req = storage.create_permission_request(q.id, "Write", {"file_path": "/x"})
    storage.decide_permission_request(req.id, allow=False)
    assert storage.get_permission_request(req.id).status == "denied"
    storage.always_allow_tool(q.id, "Write")
    storage.delete_queue(q.id)
    assert storage.get_permission_request(req.id) is None
