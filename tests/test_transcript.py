import json
from datetime import datetime

from cc_continue.transcript import TranscriptEvent, find_transcript_path, parse_transcript_events


def _line(obj: dict) -> str:
    return json.dumps(obj) + "\n"


def test_transcript_event_fields():
    event = TranscriptEvent(kind="human", text="ahoj", timestamp=datetime(2026, 9, 4, 10, 30))
    assert event.kind == "human"
    assert event.text == "ahoj"
    assert event.timestamp == datetime(2026, 9, 4, 10, 30)


def test_find_transcript_path_locates_by_session_id(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path)
    project_dir = tmp_path / "-home-lukas-DEV-some-project"
    project_dir.mkdir()
    transcript_file = project_dir / "9219c2bb-c393-4aed-ab94-fdab69a93891.jsonl"
    transcript_file.write_text("")

    found = find_transcript_path("9219c2bb-c393-4aed-ab94-fdab69a93891")
    assert found == transcript_file


def test_find_transcript_path_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path)
    assert find_transcript_path("nonexistent-session-id") is None


def test_parses_human_text_turn(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(
        _line(
            {
                "type": "user",
                "message": {"role": "user", "content": "ahoj"},
                "timestamp": "2026-09-04T10:30:00.000Z",
            }
        )
    )
    events, offset = parse_transcript_events(path)
    assert len(events) == 1
    assert events[0].kind == "human"
    assert events[0].text == "ahoj"
    assert offset == path.stat().st_size


def test_skips_user_turn_with_list_content_tool_result(tmp_path):
    # A "user" role entry whose content is a list of blocks is Claude's
    # own tool-result feedback being fed back into the model, not
    # something the human typed — must not appear as a human turn.
    path = tmp_path / "t.jsonl"
    path.write_text(
        _line(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "content": "some output"}],
                },
                "timestamp": "2026-09-04T10:30:00.000Z",
            }
        )
    )
    events, _ = parse_transcript_events(path)
    assert events == []


def test_parses_assistant_text_block(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(
        _line(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "LIVEDELIVERY"}]},
                "timestamp": "2026-09-04T10:31:00.000Z",
            }
        )
    )
    events, _ = parse_transcript_events(path)
    assert len(events) == 1
    assert events[0].kind == "assistant_text"
    assert events[0].text == "LIVEDELIVERY"


def test_skips_thinking_block(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(
        _line(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "hmm"}]},
                "timestamp": "2026-09-04T10:31:00.000Z",
            }
        )
    )
    events, _ = parse_transcript_events(path)
    assert events == []


def test_parses_tool_use_block_with_truncated_preview(tmp_path):
    path = tmp_path / "t.jsonl"
    long_command = "x" * 200
    path.write_text(
        _line(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Bash", "input": {"command": long_command}}
                    ],
                },
                "timestamp": "2026-09-04T10:31:00.000Z",
            }
        )
    )
    events, _ = parse_transcript_events(path)
    assert len(events) == 1
    assert events[0].kind == "tool_call"
    assert events[0].text.startswith("Bash: ")
    assert events[0].text.endswith("…")
    assert len(events[0].text) <= len("Bash: ") + 80 + 1


def test_skips_non_conversational_line_types(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(
        _line({"type": "cost-state", "sessionId": "x", "totalCostUSD": 0.1})
        + _line({"type": "system", "subtype": "init"})
    )
    events, _ = parse_transcript_events(path)
    assert events == []


def test_incremental_read_resumes_from_offset(tmp_path):
    path = tmp_path / "t.jsonl"
    first = _line({"type": "user", "message": {"role": "user", "content": "one"}, "timestamp": "2026-09-04T10:00:00.000Z"})
    path.write_text(first)
    events1, offset1 = parse_transcript_events(path)
    assert [e.text for e in events1] == ["one"]

    second = _line({"type": "user", "message": {"role": "user", "content": "two"}, "timestamp": "2026-09-04T10:01:00.000Z"})
    with open(path, "a") as f:
        f.write(second)

    events2, offset2 = parse_transcript_events(path, since_byte_offset=offset1)
    assert [e.text for e in events2] == ["two"]
    assert offset2 > offset1


def test_incomplete_trailing_line_not_consumed(tmp_path):
    path = tmp_path / "t.jsonl"
    complete = _line({"type": "user", "message": {"role": "user", "content": "one"}, "timestamp": "2026-09-04T10:00:00.000Z"})
    incomplete = '{"type": "user", "message": {"role": "user", "content": "cut off'  # no trailing newline, invalid JSON
    path.write_text(complete + incomplete)

    events, offset = parse_transcript_events(path)
    assert [e.text for e in events] == ["one"]
    assert offset == len(complete.encode("utf-8"))  # stopped before the incomplete line

    # once the line is completed (e.g. by the live process finishing its write), a
    # re-parse from the same offset picks it up
    with open(path, "a") as f:
        f.write(' resumed"}, "timestamp": "2026-09-04T10:02:00.000Z"}\n')
    events2, offset2 = parse_transcript_events(path, since_byte_offset=offset)
    assert len(events2) == 1
    assert events2[0].text == "cut off resumed"
    assert offset2 == path.stat().st_size
