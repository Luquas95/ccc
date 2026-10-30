import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from ccc import api
from ccc.models import QueueStatus
from ccc.storage import Storage
from ccc.usage_api import ProUsage, WindowUsage


@pytest.fixture
def storage(tmp_path):
    return Storage(str(tmp_path / "ccc.db"))


@pytest.fixture
def projects(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    (root / "-p").mkdir(parents=True)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", root)
    return root / "-p"


def _queue(storage, tmp_path, name="shop", session="s1"):
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    return storage.create_queue(name, str(folder), session)


def _transcript_line(role, text, minute=0):
    return json.dumps({
        "type": role,
        "message": {"role": role, "content": text if role == "user" else [{"type": "text", "text": text}]},
        "timestamp": f"2026-10-21T10:{minute:02d}:00.000Z",
    }) + "\n"


def test_only_the_tokens_fingerprint_is_kept_and_a_new_one_replaces_it(storage):
    assert not api.has_token(storage)
    first = api.new_token(storage)
    assert len(first) > 30
    assert first not in storage.get_setting(api.TOKEN_KEY)
    assert api.token_valid(storage, first)
    second = api.new_token(storage)
    assert api.token_valid(storage, second)
    assert not api.token_valid(storage, first)
    assert not api.token_valid(storage, "")


def test_conversations_list_with_state(storage, tmp_path):
    q = _queue(storage, tmp_path)
    storage.add_queue_item(q.id, "go on")
    storage.create_permission_request(q.id, "Bash", {"command": "ls"})
    archived = _queue(storage, tmp_path, "old", "s2")
    storage.set_queue_archived(archived.id, True)

    listed = api.Api(storage).conversations()

    assert [c["name"] for c in listed] == ["shop"]
    assert listed[0]["pending"] == 1
    assert listed[0]["needs_approval"] is True
    assert listed[0]["status"] == "idle"
    assert [c["name"] for c in api.Api(storage).conversations(archived=True)] == ["old"]


def test_conversations_carry_their_own_group(storage, tmp_path):
    q = _queue(storage, tmp_path)
    storage.set_conversation_group(q.id, "Release")

    listed = api.Api(storage).conversations()

    assert listed[0]["group"] == {"key": "own:Release", "title": "Release"}


def test_conversation_detail_has_queued_messages_and_approvals(storage, tmp_path):
    q = _queue(storage, tmp_path)
    storage.add_queue_item(q.id, "first")
    request = storage.create_permission_request(q.id, "Edit", {"file_path": "a.py"})

    detail = api.Api(storage).conversation(q.id)

    assert [m["text"] for m in detail["queued"]] == ["first"]
    assert detail["permissions"][0]["id"] == request.id
    assert detail["permissions"][0]["input"] == {"file_path": "a.py"}


def test_unknown_conversation_is_404(storage):
    with pytest.raises(api.ApiError) as error:
        api.Api(storage).route("GET", "/api/v1/conversations/99", {}, {})
    assert error.value.status == 404


def test_messages_new_ones_after_an_index_and_older_before(storage, tmp_path, projects):
    q = _queue(storage, tmp_path)
    path = projects / "s1.jsonl"
    path.write_text("".join(_transcript_line("user" if i % 2 == 0 else "assistant", f"m{i}", i) for i in range(6)))
    endpoint = api.Api(storage)

    everything = endpoint.messages(q.id)
    assert everything["total"] == 6
    assert [m["text"] for m in everything["messages"]] == [f"m{i}" for i in range(6)]
    assert everything["messages"][0]["kind"] == "human"
    assert everything["messages"][1]["kind"] == "assistant_text"

    assert [m["index"] for m in endpoint.messages(q.id, limit=2)["messages"]] == [4, 5]
    assert [m["index"] for m in endpoint.messages(q.id, before=4, limit=2)["messages"]] == [2, 3]

    with path.open("a") as f:
        f.write(_transcript_line("assistant", "m6", 6))
    assert [m["text"] for m in endpoint.messages(q.id, after=5)["messages"]] == ["m6"]


def test_messages_of_a_conversation_without_a_transcript(storage, tmp_path, projects):
    q = _queue(storage, tmp_path)
    assert api.Api(storage).messages(q.id) == {"total": 0, "messages": []}


def test_send_queues_the_message_and_resumes_a_paused_conversation(storage, tmp_path):
    q = _queue(storage, tmp_path)
    storage.update_queue_status(q.id, QueueStatus.PAUSED_LIMIT)

    status, result = api.Api(storage).route("POST", f"/api/v1/conversations/{q.id}/messages", {},
                                            {"text": "  go on  "})

    assert status == 201
    assert result["text"] == "go on"
    assert [i.prompt_text for i in storage.list_pending_items(q.id)] == ["go on"]
    assert storage.get_queue(q.id).status == QueueStatus.IDLE


def test_send_refuses_an_empty_message(storage, tmp_path):
    q = _queue(storage, tmp_path)
    with pytest.raises(api.ApiError) as error:
        api.Api(storage).send(q.id, {"text": "   "})
    assert error.value.status == 400
    assert storage.list_pending_items(q.id) == []


@pytest.mark.parametrize("decision, status, always", [
    ("allow", "allowed", False), ("always", "allowed", True), ("deny", "denied", False),
])
def test_decide_an_approval(storage, tmp_path, decision, status, always):
    q = _queue(storage, tmp_path)
    request = storage.create_permission_request(q.id, "Bash", {"command": "ls"})
    endpoint = api.Api(storage)
    assert [p["conversation"] for p in endpoint.permissions()] == ["shop"]

    endpoint.decide(request.id, {"decision": decision})

    assert storage.get_permission_request(request.id).status == status
    assert storage.is_tool_always_allowed(q.id, "Bash") is always
    assert endpoint.permissions() == []
    with pytest.raises(api.ApiError) as error:
        endpoint.decide(request.id, {"decision": "allow"})
    assert error.value.status == 409


def test_decide_needs_a_known_decision(storage, tmp_path):
    q = _queue(storage, tmp_path)
    request = storage.create_permission_request(q.id, "Bash", {})
    with pytest.raises(api.ApiError) as error:
        api.Api(storage).decide(request.id, {"decision": "maybe"})
    assert error.value.status == 400
    assert storage.get_permission_request(request.id).status == "pending"


def test_create_a_conversation_with_defaults_and_a_first_message(storage, tmp_path):
    folder = tmp_path / "new"
    folder.mkdir()

    status, result = api.Api(storage).route("POST", "/api/v1/conversations", {}, {
        "path": str(folder), "options": ["model_sonnet"], "interactive": False, "prompt": "hello",
    })

    assert status == 201
    queue = storage.get_queue(result["id"])
    assert queue.name == "new"
    assert queue.delivery_mode.value == "headless"
    # The session and permission choices were missing: the defaults.
    assert queue.launch_flags == ["--dangerously-skip-permissions", "--model", "sonnet"]
    assert result["queued"][0]["text"] == "hello"


@pytest.mark.parametrize("body", [
    {"path": ""},
    {"path": "/no/such/folder"},
    {"path": "/tmp", "options": ["model_opus", "model_haiku"]},
    {"path": "/tmp", "options": ["nonsense"]},
    {"path": "/tmp", "options": "model_opus"},
])
def test_create_refuses_a_bad_request(storage, body):
    with pytest.raises(api.ApiError) as error:
        api.Api(storage).create(body)
    assert error.value.status == 400
    assert storage.list_queues() == []


def test_launch_options_and_projects(storage, tmp_path):
    _queue(storage, tmp_path)
    endpoint = api.Api(storage)

    options = endpoint.launch_options()

    assert options["groups"][0]["key"] == "session"
    assert {"key": "model_opus", "label": "Opus"} in options["groups"][3]["options"]
    assert "perm_skip" in options["default"]
    assert endpoint.projects() == [str(tmp_path / "shop")]


def test_usage(storage, monkeypatch):
    resets = datetime(2026, 10, 21, 20, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("ccc.usage_api.get_pro_usage",
                        lambda force_refresh=False: ProUsage(WindowUsage(64.0, resets), None, []))

    usage = api.Api(storage).usage()

    assert usage == {"five_hour": {"percent": 64.0, "resets_at": resets.isoformat()},
                     "seven_day": None, "per_model": []}


def test_changes_name_the_conversations_that_changed(storage, tmp_path, projects):
    q = _queue(storage, tmp_path)
    other = _queue(storage, tmp_path, "docs", "s2")
    endpoint = api.Api(storage)
    before = endpoint.snapshot()
    assert endpoint.changes(before, endpoint.snapshot()) is None

    storage.add_queue_item(q.id, "next")
    (projects / "s2.jsonl").write_text(_transcript_line("user", "hi"))
    endpoint._transcripts.clear()  # look the new transcript up now
    storage.delete_queue(other.id)

    assert endpoint.changes(before, endpoint.snapshot()) == {"conversations": [q.id], "removed": [other.id]}


# --- over HTTP ------------------------------------------------------------------


@pytest.fixture
def server(storage):
    httpd = api.make_server(storage, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", api.new_token(storage)
    httpd.shutdown()
    httpd.server_close()


def _call(url, token=None, method="GET", body=None):
    request = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_http_needs_the_token(server):
    base, token = server
    assert _call(f"{base}/api/v1/status")[0] == 401
    assert _call(f"{base}/api/v1/status", "wrong")[0] == 401
    status, result = _call(f"{base}/api/v1/status", token)
    assert status == 200
    assert result["daemon_running"] is False


def test_http_a_new_token_locks_the_old_one_out(server, storage):
    base, token = server
    newer = api.new_token(storage)
    assert _call(f"{base}/api/v1/status", token)[0] == 401
    assert _call(f"{base}/api/v1/status", newer)[0] == 200


def test_http_send_and_read_back(server, storage, tmp_path):
    base, token = server
    q = _queue(storage, tmp_path)

    status, _ = _call(f"{base}/api/v1/conversations/{q.id}/messages", token, "POST", {"text": "hello"})
    assert status == 201
    status, result = _call(f"{base}/api/v1/conversations/{q.id}", token)
    assert status == 200
    assert [m["text"] for m in result["queued"]] == ["hello"]


def test_http_errors_are_json(server):
    base, token = server
    assert _call(f"{base}/api/v1/nothing", token) == (404, {"error": "Not found."})
    assert _call(f"{base}/api/v1/conversations/x/messages", token)[0] == 404
    assert _call(f"{base}/api/v1/conversations/1/messages?after=x", token)[0] == 400


def test_http_events_stream_tells_about_a_change(server, storage, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "EVENTS_POLL_SECONDS", 0.05)
    base, token = server
    q = _queue(storage, tmp_path)
    request = urllib.request.Request(f"{base}/api/v1/events", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=5) as stream:
        assert stream.headers["Content-Type"] == "text/event-stream"
        assert stream.readline() == b": connected\n"
        stream.readline()
        storage.add_queue_item(q.id, "next")
        assert stream.readline() == b"event: changed\n"
        assert json.loads(stream.readline().removeprefix(b"data: ")) == {"conversations": [q.id], "removed": []}


def test_retry_and_seen(storage, tmp_path):
    q = _queue(storage, tmp_path)
    storage.update_queue_status(q.id, QueueStatus.BLOCKED_ERROR, last_error="boom")
    endpoint = api.Api(storage)

    assert endpoint.route("POST", f"/api/v1/conversations/{q.id}/retry", {}, {}) == (200, {"retried": True})
    assert storage.get_queue(q.id).status == QueueStatus.IDLE
    assert endpoint.route("POST", f"/api/v1/conversations/{q.id}/seen", {}, {})[0] == 200
    assert storage.get_queue(q.id).last_seen_at > datetime.now() - timedelta(minutes=1)


def test_http_events_stream_ends_when_a_new_token_is_made(server, storage, monkeypatch):
    monkeypatch.setattr(api, "EVENTS_POLL_SECONDS", 0.05)
    base, token = server
    request = urllib.request.Request(f"{base}/api/v1/events", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=5) as stream:
        assert stream.readline() == b": connected\n"
        api.new_token(storage)
        assert stream.read() == b"\n"  # the blank line after "connected", then closed


def test_cli_shows_a_token_only_when_it_makes_one(storage, capsys):
    from argparse import Namespace

    from ccc import api_cli

    api_cli.run(storage, "", Namespace(api_command="token", new=False))
    made = capsys.readouterr().out.splitlines()[0]
    assert api.token_valid(storage, made)
    api_cli.run(storage, "", Namespace(api_command="token", new=False))
    assert made not in capsys.readouterr().out
    api_cli.run(storage, "", Namespace(api_command="token", new=True))
    assert not api.token_valid(storage, made)


# --- round 1: managing conversations ---------------------------------------------


def test_archive_and_restore(storage, tmp_path):
    q = _queue(storage, tmp_path)
    endpoint = api.Api(storage)

    assert endpoint.route("POST", f"/api/v1/conversations/{q.id}/archive", {}, {"archived": True})[1]["archived"]
    assert endpoint.conversations() == []
    endpoint.archive(q.id, {"archived": False})
    assert [c["id"] for c in endpoint.conversations()] == [q.id]
    with pytest.raises(api.ApiError) as error:
        endpoint.archive(q.id, {"archived": "yes"})
    assert error.value.status == 400


def test_delete_but_not_while_it_runs(storage, tmp_path):
    q = _queue(storage, tmp_path)
    storage.update_queue_status(q.id, QueueStatus.RUNNING)
    endpoint = api.Api(storage)
    with pytest.raises(api.ApiError) as error:
        endpoint.route("DELETE", f"/api/v1/conversations/{q.id}", {}, {})
    assert error.value.status == 409

    storage.update_queue_status(q.id, QueueStatus.IDLE)
    assert endpoint.route("DELETE", f"/api/v1/conversations/{q.id}", {}, {}) == (200, {"deleted": q.id})
    assert storage.find_queue(q.id) is None


def test_own_groups_put_rename_delete(storage, tmp_path):
    q = _queue(storage, tmp_path)
    other = _queue(storage, tmp_path, "docs", "s2")
    endpoint = api.Api(storage)

    endpoint.set_group(q.id, {"name": " Release "})
    endpoint.set_group(other.id, {"name": "Release"})
    assert endpoint.groups() == {"mode": "own", "own": ["Release"]}
    assert {c["group"]["title"] for c in endpoint.conversations()} == {"Release"}
    assert endpoint.conversation(q.id)["group"] == {"key": "own:Release", "title": "Release"}

    endpoint.rename_group({"old": "Release", "new": "v2"})
    assert endpoint.groups()["own"] == ["v2"]
    endpoint.set_group(other.id, {"name": None})
    assert storage.conversation_groups() == {q.id: "v2"}
    endpoint.delete_group({"name": "v2"})
    assert endpoint.groups()["own"] == []
    with pytest.raises(api.ApiError):
        endpoint.rename_group({"old": "", "new": "x"})


def test_search_export_and_files(storage, tmp_path, projects):
    q = _queue(storage, tmp_path)
    (projects / "s1.jsonl").write_text(_transcript_line("user", "Add rate limiting") +
                                       _transcript_line("assistant", "Rate limiting added", 1))
    (tmp_path / "shop" / "src").mkdir()
    (tmp_path / "shop" / "src" / "limits.py").write_text("")
    endpoint = api.Api(storage)

    hits = endpoint.route("GET", "/api/v1/search", {"q": "rate LIMITING"}, {})[1]
    assert [h["kind"] for h in hits] == ["assistant_text", "human"]
    assert hits[0]["conversation_id"] == q.id

    exported = endpoint.export(q.id)
    assert exported["filename"].startswith("shop-") and exported["filename"].endswith(".md")
    assert "Rate limiting added" in exported["markdown"]

    assert endpoint.files(q.id, "limit") == ["src/limits.py"]


def test_waiting_prompt_presets_and_sessions(storage, tmp_path, projects, monkeypatch):
    from ccc.prompt_presets import PromptPreset, save_prompt_presets

    q = _queue(storage, tmp_path)
    storage.create_permission_request(q.id, "Bash", {})
    save_prompt_presets(storage, [PromptPreset("Tests", "Run the tests", send_now=True)])
    endpoint = api.Api(storage)

    assert endpoint.waiting() == [{"conversation_id": q.id, "name": "shop", "kind": "approval",
                                   "label": "waits for approval"}]
    assert endpoint.prompt_presets() == [{"number": 1, "name": "Tests", "text": "Run the tests", "send_now": True}]

    folder = tmp_path / "shop"
    session_dir = projects.parent / api_encode(str(folder))
    session_dir.mkdir()
    (session_dir / "abc.jsonl").write_text(_transcript_line("user", "first prompt"))
    sessions = endpoint.sessions(str(folder))
    assert [(s["session_id"], s["first_prompt"]) for s in sessions] == [("abc", "first prompt")]
    assert endpoint.sessions("/no/such") == []


def api_encode(path):
    from ccc.transcript import encode_project_dir

    return encode_project_dir(path)


def test_creating_remembers_the_choice_like_the_tui(storage, tmp_path):
    folder = tmp_path / "new"
    folder.mkdir()
    endpoint = api.Api(storage)
    assert endpoint.launch_presets() == {"last": None, "presets": []}

    endpoint.create({"path": str(folder), "options": ["model_opus"], "interactive": False, "auto_continue": False})

    last = endpoint.launch_presets()["last"]
    assert "model_opus" in last["options"] and last["auto_continue"] is False


# --- round 2: the task queue, runs, diffs ------------------------------------------


def test_tasks_add_edit_move_remove_and_switches(storage, tmp_path):
    q = _queue(storage, tmp_path)
    endpoint = api.Api(storage)

    first = endpoint.route("POST", f"/api/v1/conversations/{q.id}/tasks", {}, {"text": " one ", "when": ""})[1]
    second = endpoint.add_task(q.id, {"text": "two", "when": "2030-01-02 03:04"})
    assert second["not_before"] == "2030-01-02T03:04:00"
    assert [t["text"] for t in endpoint.tasks(q.id)["tasks"]] == ["one", "two"]

    endpoint.move_task(second["id"], {"delta": -1})
    endpoint.edit_task(first["id"], {"text": "one, better", "when": "2030-05-06 07:08"})
    listed = endpoint.tasks(q.id)["tasks"]
    assert [(t["text"], t["not_before"]) for t in listed] == [("two", "2030-01-02T03:04:00"),
                                                              ("one, better", "2030-05-06T07:08:00")]
    endpoint.route("DELETE", f"/api/v1/tasks/{second['id']}", {}, {})
    assert [t["text"] for t in endpoint.tasks(q.id)["tasks"]] == ["one, better"]

    switches = endpoint.switches(q.id, {"paused": True, "auto_continue": False})
    assert (switches["paused"], switches["auto_continue"]) == (True, False)
    assert storage.get_queue(q.id).paused


@pytest.mark.parametrize("call", [
    lambda e, q, i: e.add_task(q, {"text": "  "}),
    lambda e, q, i: e.add_task(q, {"text": "x", "when": "tomorrow-ish"}),
    lambda e, q, i: e.move_task(i, {"delta": 3}),
    lambda e, q, i: e.switches(q, {"paused": "yes"}),
    lambda e, q, i: e.edit_task(i, {"text": ""}),
])
def test_tasks_refuse_bad_input(storage, tmp_path, call):
    q = _queue(storage, tmp_path)
    item = storage.add_queue_item(q.id, "keep")
    with pytest.raises(api.ApiError) as error:
        call(api.Api(storage), q.id, item.id)
    assert error.value.status == 400
    assert [i.prompt_text for i in storage.list_pending_items(q.id)] == ["keep"]


def test_a_started_task_cant_be_changed(storage, tmp_path):
    from ccc.models import ItemStatus

    q = _queue(storage, tmp_path)
    item = storage.add_queue_item(q.id, "running")
    storage.set_item_status(item.id, ItemStatus.RUNNING)
    with pytest.raises(api.ApiError) as error:
        api.Api(storage).remove_task(item.id)
    assert error.value.status == 409


def _git(cwd, *args):
    import subprocess

    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo_run(storage, tmp_path):
    from ccc.models import PromptRun, RunStatus

    repo = tmp_path / "calc"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    _git(repo, "commit", "-qam", "ccc: subtract")
    queue = storage.create_queue("calc", str(repo), "s-calc")
    run_id = storage.insert_prompt_run(PromptRun(
        id=0, queue_id=queue.id, queue_item_id=None, prompt_text="Make add subtract\nplease", started_at=datetime.now(),
        finished_at=datetime.now(), status=RunStatus.SUCCESS, input_tokens=10, output_tokens=5,
        git_commit=_git(repo, "rev-parse", "HEAD"),
    ))
    return queue, run_id, repo


def test_runs_diff_and_comments_to_claude(storage, repo_run):
    queue, run_id, _repo = repo_run
    endpoint = api.Api(storage)

    runs = endpoint.runs(queue.id)
    assert [(r["id"], r["status"], r["tokens"]) for r in runs] == [(run_id, "success", 15)]

    diff = endpoint.diff(run_id)
    assert diff["task"] == "Make add subtract"
    added = next(line for line in diff["lines"] if line["kind"] == "added")
    assert added["text"] == "+    return a - b" and added["path"] == "calc.py" and added["new_line"] == 2

    status, sent = endpoint.route("POST", f"/api/v1/runs/{run_id}/comments", {},
                                  {"comments": [{"index": added["index"], "text": "keep adding"}]})
    assert status == 201 and sent["comments"] == 1
    prompt = storage.list_pending_items(queue.id)[0].prompt_text
    assert "calc.py:2" in prompt and "keep adding" in prompt
    header = next(line for line in diff["lines"] if not line["commentable"])
    with pytest.raises(api.ApiError):
        endpoint.comment(run_id, {"comments": [{"index": header["index"], "text": "no"}]})


def test_revert_a_run_and_tell_claude(storage, repo_run):
    queue, run_id, repo = repo_run
    endpoint = api.Api(storage)

    commit = endpoint.revert(run_id, {"tell": True})["commit"]

    assert (repo / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    assert storage.find_run(run_id).reverted_by == commit
    assert "reverted" in storage.list_pending_items(queue.id)[0].prompt_text
    with pytest.raises(api.ApiError) as error:
        endpoint.revert(run_id, {})
    assert error.value.status == 409


def test_no_diff_where_claude_may_not_run_commands(storage, repo_run):
    queue, run_id, _repo = repo_run
    with storage._connect() as conn:
        conn.execute("UPDATE queues SET launch_flags = ? WHERE id = ?", ('["--permission-mode", "plan"]', queue.id))
    endpoint = api.Api(storage)
    with pytest.raises(api.ApiError) as error:
        endpoint.diff(run_id)
    assert error.value.status == 409
    with pytest.raises(api.ApiError):
        endpoint.comment(run_id, {"comments": [{"index": 0, "text": "x"}]})


def test_mcp_servers_lists_names_only(storage, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    (tmp_path / ".claude.json").write_text('{"mcpServers": {"db": {"command": "x", "env": {"TOKEN": "secret"}}}}')
    endpoint = api.Api(storage)

    assert endpoint.mcp_servers(str(tmp_path)) == ["db"]
    assert endpoint.mcp_servers("") == []


def test_create_stores_the_chosen_mcp_servers_as_a_marker(storage, tmp_path):
    folder = tmp_path / "shop"
    folder.mkdir()

    result = api.Api(storage).create({
        "path": str(folder), "options": ["mcp_select", "mcp:db"], "interactive": False, "auto_continue": False,
    })

    assert storage.get_queue(result["id"]).launch_flags == ["--dangerously-skip-permissions", "--ccc-mcp=db"]


def test_conversations_carry_context_and_git(storage, tmp_path, monkeypatch):
    from ccc import gitops
    from ccc.context_fill import ContextFill, ContextTracker

    q = _queue(storage, tmp_path)  # a legacy queue: Claude may run commands here
    calls = []
    monkeypatch.setattr(ContextTracker, "fills", lambda self, st, queues: {x.id: ContextFill(186_000, 200_000) for x in queues})
    monkeypatch.setattr(gitops, "work_status", lambda cwd: calls.append(cwd) or gitops.WorkStatus(12, 3, 2, 0, "origin/main", "feature-x"))
    server = api.Api(storage)

    listed = server.conversations()[0]
    assert listed["context"] == {"tokens": 186_000, "percent": 93, "level": "danger"}
    assert listed["git"] == {"branch": "feature-x", "added": 12, "removed": 3, "ahead": 2, "behind": 0}
    server.conversations()
    server.conversation(q.id)
    assert len(calls) == 1  # looked up once per folder in GIT_SECONDS
    monkeypatch.setattr(api, "GIT_SECONDS", 0.0)
    server.conversations()
    assert len(calls) == 2


def test_no_context_and_no_git_where_claude_may_not_run_commands(storage, tmp_path, monkeypatch):
    from ccc import gitops

    q = _queue(storage, tmp_path)
    monkeypatch.setattr(gitops, "claude_can_run_commands", lambda queue: False)
    monkeypatch.setattr(gitops, "work_status", lambda cwd: pytest.fail("git must not run here"))
    listed = api.Api(storage).conversations()[0]
    assert listed["git"] is None and listed["context"] is None  # no transcript either
