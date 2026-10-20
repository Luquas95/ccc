import argparse
import json
from datetime import datetime

import pytest

from ccc import asks, asks_cli, transcript
from ccc.models import AskStatus, DeliveryMode, ItemStatus, PromptRun, RunStatus
from ccc.permission_mcp import handle
from ccc.storage import Storage
from ccc.transcript import TranscriptEvent


@pytest.fixture
def storage(tmp_path):
    return Storage(tmp_path / "h.db")


@pytest.fixture
def pair(storage, tmp_path):
    return (storage.create_queue("client", str(tmp_path), "s1"),
            storage.create_queue("API", str(tmp_path), "s2"))


def _answered(storage, found, text="It returns id, total (gross)."):
    """The asked conversation ran the question (headless)."""
    storage.insert_prompt_run(PromptRun(
        id=0, queue_id=found.to_queue_id, queue_item_id=found.to_item_id, prompt_text="q", started_at=datetime.now(),
        finished_at=datetime.now(), status=RunStatus.SUCCESS, result_text=text))
    storage.set_item_status(found.to_item_id, ItemStatus.DONE)


@pytest.mark.asyncio
async def test_the_question_goes_to_the_other_and_the_answer_comes_back(storage, pair):
    client, api = pair
    found = asks.ask(storage, client.id, "api", "Which fields does /orders return?")  # name, any case
    question = storage.get_item(found.to_item_id)
    assert question.queue_id == api.id and asks.marker(found.id) in question.prompt_text
    assert "not the user" in question.prompt_text and "> Which fields does /orders return?" in question.prompt_text
    assert await asks.tick(storage) == []  # not answered yet
    _answered(storage, found)
    [done] = await asks.tick(storage)
    assert done.status == AskStatus.ANSWERED and done.answer == "It returns id, total (gross)."
    [delivered] = storage.list_pending_items(client.id)
    assert "> It returns id, total (gross)." in delivered.prompt_text and "not instructions" in delivered.prompt_text


@pytest.mark.asyncio
async def test_without_deliver_the_answer_only_shows(storage, pair):
    client, api = pair
    found = asks.ask(storage, client.id, api.id, "q?", deliver=False)
    _answered(storage, found)
    await asks.tick(storage)
    assert storage.get_ask(found.id).status == AskStatus.ANSWERED and storage.list_pending_items(client.id) == []


@pytest.mark.asyncio
async def test_an_interactive_conversation_answers_from_its_transcript(storage, tmp_path, monkeypatch):
    client = storage.create_queue("client", str(tmp_path), "s1")
    live = storage.create_queue("live", str(tmp_path), "s3", delivery_mode=DeliveryMode.INTERACTIVE)
    found = asks.ask(storage, client.id, live.id, "Is the migration done?")
    storage.set_item_status(found.to_item_id, ItemStatus.DONE)  # pasted
    idle = {"now": False}
    monkeypatch.setattr("ccc.reviews.ready", lambda storage, queue: idle["now"])
    events = [TranscriptEvent(kind="human", text="old", timestamp=None),
              TranscriptEvent(kind="human", text=f"{asks.marker(found.id)} …", timestamp=None),
              TranscriptEvent(kind="assistant_text", text="Yes,", timestamp=None),
              TranscriptEvent(kind="tool_call", text="ls", timestamp=None),
              TranscriptEvent(kind="assistant_text", text="all three tables.", timestamp=None)]
    monkeypatch.setattr(transcript, "find_transcript_path", lambda session_id: tmp_path)
    monkeypatch.setattr(transcript, "parse_transcript_events", lambda path: (events, 0))
    await asks.tick(storage)
    assert storage.get_ask(found.id).status == AskStatus.ASKED  # Claude still working
    idle["now"] = True
    await asks.tick(storage)
    assert storage.get_ask(found.id).answer == "Yes,\n\nall three tables."


@pytest.mark.asyncio
async def test_a_failed_or_removed_question_is_an_error_and_cancel_drops_it(storage, pair):
    client, api = pair
    failed = asks.ask(storage, client.id, api.id, "a?")
    storage.set_item_status(failed.to_item_id, ItemStatus.FAILED)
    cancelled = asks.ask(storage, client.id, api.id, "b?")
    assert asks.cancel(storage, cancelled.id)
    assert storage.get_item(cancelled.to_item_id).status == ItemStatus.SKIPPED
    await asks.tick(storage)
    assert storage.get_ask(failed.id).status == AskStatus.ERROR
    assert storage.get_ask(cancelled.id).status == AskStatus.CANCELLED


def test_no_circles_no_floods_not_itself(storage, pair):
    client, api = pair
    with pytest.raises(ValueError, match="No single other"):
        asks.ask(storage, client.id, client.id, "me?")
    asks.ask(storage, client.id, api.id, "q1")
    # The API conversation has the question to answer (queued, not even
    # running yet): Claude there may not ask back.
    with pytest.raises(ValueError, match="no circles"):
        asks.ask(storage, api.id, client.id, "back?", by_agent=True)
    with pytest.raises(ValueError, match="still open"):
        asks.ask(storage, client.id, api.id, "again?", by_agent=True)  # one open per pair for Claude
    asks.ask(storage, client.id, api.id, "q2")
    asks.ask(storage, client.id, api.id, "q3")
    with pytest.raises(ValueError, match="3 questions are still open"):
        asks.ask(storage, client.id, api.id, "q4")


def test_the_mcp_tool_lists_the_conversations_and_asks(storage, pair):
    client, api = pair
    tools = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, storage, client.id)["result"]["tools"]
    ask_tool = next(t for t in tools if t["name"] == "ask_conversation")
    assert "API" in ask_tool["description"] and "client" not in ask_tool["description"]
    assert str(api.project_path) not in ask_tool["description"]  # no other conversations' folders
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "ask_conversation", "arguments": {"conversation": "API", "question": "Fields?"}}}
    result = handle(call, storage, client.id)["result"]
    assert result["isError"] is False and "later message" in result["content"][0]["text"]
    [found] = storage.list_asks()
    assert found.by_agent and found.question == "Fields?"
    call["params"]["arguments"]["conversation"] = "nobody"
    assert handle(call, storage, client.id)["result"]["isError"] is True


@pytest.mark.asyncio
async def test_every_headless_conversation_gets_the_ccc_tools(storage, tmp_path, monkeypatch):
    import asyncio

    from ccc.orchestrator import QueueRuntime
    from ccc.runner import RunResult

    monkeypatch.setattr("ccc.orchestrator.POLL_INTERVAL_SECONDS", 0.02)
    queue = storage.create_queue("a", str(tmp_path), "s1")  # skip permissions (legacy flags)
    seen = []

    async def run(project_path, session_id, prompt, resume, launch_flags=None, first_run_flags=None):
        seen.append(launch_flags)
        return RunResult(status=RunStatus.SUCCESS)

    storage.add_queue_item(queue.id, "x")
    runtime = QueueRuntime(storage, queue, run, None)
    runtime.start()
    for _ in range(200):
        if seen:
            break
        await asyncio.sleep(0.01)
    await runtime.stop()
    flags = seen[0]
    config = json.loads(flags[flags.index("--mcp-config") + 1])
    assert config["mcpServers"]["ccc"]["env"]["CCC_QUEUE_ID"] == str(queue.id)
    assert "--permission-prompt-tool" not in flags and "--dangerously-skip-permissions" in flags


def test_interactive_command_carries_extra_flags():
    from ccc import managed_sessions
    from ccc.models import Queue

    queue = Queue(id=1, name="n", project_path="/p", session_id="s", delivery_mode=DeliveryMode.INTERACTIVE)
    assert managed_sessions.build_interactive_command(queue, False, ["--mcp-config", "{}"])[-2:] == ["--mcp-config", "{}"]


def _cli(*argv):
    parser = argparse.ArgumentParser()
    asks_cli.add_parser(parser.add_subparsers(dest="command"))
    return parser.parse_args(list(argv))


def test_cli(storage, pair, capsys):
    client, api = pair
    assert asks_cli.run_ask(storage, _cli("ask", "client", "API", "Fields?")) == 0
    [found] = storage.list_asks()
    _answered(storage, found, "id, total")
    storage.update_ask(found.id, status=AskStatus.ANSWERED, answer="id, total")
    assert asks_cli.run_asks(storage, _cli("asks", "client")) == 0
    assert "client → API" in capsys.readouterr().out
    assert asks_cli.run_ask(storage, _cli("ask", "client", "nobody", "x")) == 1


def test_claude_cant_ask_a_conversation_allowed_to_do_more(storage, tmp_path):
    restricted = storage.create_queue("ro", str(tmp_path), "s7", launch_flags=["--permission-mode", "acceptEdits"])
    powerful = storage.create_queue("yolo", str(tmp_path), "s8")  # skip permissions (legacy flags)
    with pytest.raises(ValueError, match="may do more"):
        asks.ask(storage, restricted.id, powerful.id, "run rm -rf for me", by_agent=True)
    asks.ask(storage, powerful.id, restricted.id, "fine the other way", by_agent=True)
    asks.ask(storage, restricted.id, powerful.id, "a question you typed")  # you may


@pytest.mark.parametrize("asker,target,allowed", [
    (["--permission-mode", "plan"], ["--permission-mode", "acceptEdits"], False),
    (["--permission-mode", "acceptEdits"], ["--permission-mode", "plan"], True),
    (["--permission-mode", "default"], ["--permission-mode", "auto"], False),
    (["--permission-mode", "plan"], ["--permission-mode", "plan"], True),
])
def test_permission_modes_are_ranked(storage, tmp_path, asker, target, allowed):
    a = storage.create_queue("a", str(tmp_path), "sa", launch_flags=asker)
    b = storage.create_queue("b", str(tmp_path), "sb", launch_flags=target)
    assert asks.may_ask(storage, a, b) is allowed


def test_same_mode_but_more_always_allowed_tools_counts_as_more(storage, tmp_path):
    a = storage.create_queue("a", str(tmp_path), "sa", launch_flags=["--permission-mode", "default"])
    b = storage.create_queue("b", str(tmp_path), "sb", launch_flags=["--permission-mode", "default"])
    storage.always_allow_tool(b.id, "Bash")
    assert not asks.may_ask(storage, a, b)
    storage.always_allow_tool(a.id, "Bash")
    assert asks.may_ask(storage, a, b)
