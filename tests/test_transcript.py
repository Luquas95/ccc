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


REAL_TRANSCRIPT_JSONL = "\n".join(
    [
        json.dumps(
            {
                "parentUuid": "ed53ba40-7450-472a-8afa-78574ee6d7a5",
                "isSidechain": False,
                "promptId": "3550a5ca-3778-49d6-973b-bed1e5eb4fc9",
                "type": "user",
                "message": {"role": "user", "content": "Reply with exactly one word: LIVEDELIVERY"},
                "uuid": "b705e8a4-a01e-4f31-8fea-122ed9d1cb1c",
                "timestamp": "2026-09-04T07:52:10.929Z",
                "cwd": "/home/lukas/DEV/CC-continue",
                "sessionId": "9219c2bb-c393-4aed-ab94-fdab69a93891",
            }
        ),
        json.dumps(
            {
                "parentUuid": "b11cb09d-dd40-4e2e-857f-678e807a3f09",
                "isSidechain": False,
                "message": {
                    "model": "claude-sonnet-5",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "thinking", "thinking": "", "signature": "abc"}],
                },
                "type": "assistant",
                "uuid": "9271aa1c-dcd0-4e6f-87a9-c907c12fd19c",
                "timestamp": "2026-09-04T07:52:15.000Z",
            }
        ),
        json.dumps(
            {
                "parentUuid": "9271aa1c-dcd0-4e6f-87a9-c907c12fd19c",
                "isSidechain": False,
                "message": {
                    "model": "claude-sonnet-5",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "LIVEDELIVERY"}],
                    "stop_reason": "end_turn",
                },
                "type": "assistant",
                "uuid": "1e677807-4ce1-4254-98d4-dc6e9e426551",
                "timestamp": "2026-09-04T07:52:21.000Z",
            }
        ),
    ]
) + "\n"


def test_parses_real_captured_transcript_shape(tmp_path):
    path = tmp_path / "real.jsonl"
    path.write_text(REAL_TRANSCRIPT_JSONL)

    events, offset = parse_transcript_events(path)

    assert offset == path.stat().st_size
    assert [(e.kind, e.text) for e in events] == [
        ("human", "Reply with exactly one word: LIVEDELIVERY"),
        ("assistant_text", "LIVEDELIVERY"),
    ]


import os
import time

from cc_continue.transcript import encode_project_dir, list_sessions_for_directory


def _session_line(kind, content, ts="2026-10-12T10:00:00.000Z"):
    if kind == "user":
        return json.dumps({"type": "user", "message": {"role": "user", "content": content}, "timestamp": ts}) + "\n"
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": content}]}, "timestamp": ts}) + "\n"


def test_encode_project_dir():
    assert encode_project_dir("/mnt/AI/DEV/CC-continue") == "-mnt-AI-DEV-CC-continue"
    assert encode_project_dir("/a/b_c.d") == "-a-b-c-d"


def test_lists_sessions_newest_first_via_path_and_realpath(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", root)
    real = tmp_path / "real"; real.mkdir()
    link = tmp_path / "link"; link.symlink_to(real)
    d1 = root / encode_project_dir(str(link)); d1.mkdir(parents=True)
    d2 = root / encode_project_dir(str(real)); d2.mkdir(parents=True)
    (d1 / "old.jsonl").write_text(_session_line("user", "first old") + _session_line("assistant", "ok"))
    time.sleep(0.01)
    (d2 / "new.jsonl").write_text(_session_line("user", "<command-name>x</command-name>") + _session_line("user", "real prompt"))
    (d2 / "empty.jsonl").write_text(_session_line("assistant", "no human"))
    os.utime(d1 / "old.jsonl", (1, 1))
    sessions = list_sessions_for_directory(str(link))
    assert [s.session_id for s in sessions] == ["new", "old"]
    assert sessions[0].first_prompt == "real prompt"
    assert sessions[1].message_count == 2
