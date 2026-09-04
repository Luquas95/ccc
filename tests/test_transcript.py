from datetime import datetime

from cc_continue.transcript import TranscriptEvent, find_transcript_path


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
