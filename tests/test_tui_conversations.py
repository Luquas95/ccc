import json

import pytest
from textual.app import App
from textual.widgets import DataTable

from cc_continue.storage import Storage
from cc_continue.tui.conversations import ConversationsScreen


@pytest.mark.asyncio
async def test_shows_queue_list_and_placeholder_for_no_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    (tmp_path / "projects").mkdir()

    storage = Storage(tmp_path / "history.db")
    storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa")

    screen = ConversationsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        table = app.screen.query_one("#conversation-queue-list", DataTable)
        rows = [str(cell) for row_key in table.rows for cell in table.get_row(row_key)]
        assert any("proj-a" in cell for cell in rows)

        right_panel_text = "\n".join(
            str(s.render()) for s in app.screen.query("#conversation-transcript Static")
        )
        assert "No conversation yet." in right_panel_text


@pytest.mark.asyncio
async def test_renders_real_conversation_and_switches_on_arrow_key(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    project_dir = tmp_path / "projects" / "-tmp-proj-a"
    project_dir.mkdir(parents=True)

    storage = Storage(tmp_path / "history.db")
    storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa")
    storage.create_queue("proj-b", "/tmp/proj-b", "session-bbb")

    transcript_a = project_dir / "session-aaa.jsonl"
    transcript_a.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": "ahoj z A"},
                "timestamp": "2026-09-04T10:00:00.000Z",
            }
        )
        + "\n"
    )

    screen = ConversationsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        def right_panel_text():
            return "\n".join(str(s.render()) for s in app.screen.query("#conversation-transcript Static"))

        assert "ahoj z A" in right_panel_text()

        await pilot.press("down")
        await pilot.pause()

        assert "No conversation yet." in right_panel_text()
        assert "ahoj z A" not in right_panel_text()


@pytest.mark.asyncio
async def test_picks_up_new_transcript_lines_on_periodic_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    project_dir = tmp_path / "projects" / "-tmp-proj-a"
    project_dir.mkdir(parents=True)

    storage = Storage(tmp_path / "history.db")
    storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa")

    transcript_a = project_dir / "session-aaa.jsonl"
    transcript_a.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "first"}, "timestamp": "2026-09-04T10:00:00.000Z"})
        + "\n"
    )

    screen = ConversationsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        with open(transcript_a, "a") as f:
            f.write(
                json.dumps({"type": "user", "message": {"role": "user", "content": "second"}, "timestamp": "2026-09-04T10:01:00.000Z"})
                + "\n"
            )

        # directly invoke the refresh instead of sleeping 2 real seconds
        await screen._refresh_current()
        await pilot.pause()

        right_panel_text = "\n".join(str(s.render()) for s in app.screen.query("#conversation-transcript Static"))
        assert "first" in right_panel_text
        assert "second" in right_panel_text


@pytest.mark.asyncio
async def test_message_text_containing_markup_like_syntax_renders_literally(tmp_path, monkeypatch):
    # Regression test for a real markup-injection bug: conversation text
    # interpolated unescaped into a Rich markup string had text like
    # "[red]URGENT[/red]" silently interpreted as a style tag instead of
    # shown as the literal characters the human/model actually
    # wrote/said — confirmed with rich.console.Console before the fix.
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    project_dir = tmp_path / "projects" / "-tmp-proj-a"
    project_dir.mkdir(parents=True)

    storage = Storage(tmp_path / "history.db")
    storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa")

    transcript_a = project_dir / "session-aaa.jsonl"
    transcript_a.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": "My note says: [red]URGENT[/red] fix this"},
                "timestamp": "2026-09-04T10:00:00.000Z",
            }
        )
        + "\n"
    )

    screen = ConversationsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        right_panel_text = "\n".join(str(s.render()) for s in app.screen.query("#conversation-transcript Static"))
        assert "[red]URGENT[/red]" in right_panel_text
