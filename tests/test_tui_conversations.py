import json

import pytest
from textual.app import App
from textual.widgets import Button, DataTable

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


@pytest.mark.asyncio
async def test_sidebar_buttons_show_full_label_text(tmp_path, monkeypatch):
    # Regression test for the same markup-injection class of bug as
    # message text: Button labels are also parsed as Rich markup, so an
    # earlier draft using "Add prompt [a]" silently lost the "[a]" —
    # square brackets look like a (invalid, silently-dropped) style tag.
    # Fixed by using parentheses instead; this locks that in.
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    (tmp_path / "projects").mkdir()
    storage = Storage(tmp_path / "history.db")

    screen = ConversationsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        labels = {str(b.label) for b in app.screen.query(Button)}
        assert "New conversation (n)" in labels
        assert "Live sessions (s)" in labels
        assert "Retry blocked (r)" in labels


from textual.widgets import Input


async def _open(storage, **kw):
    screen = ConversationsScreen(storage, **kw)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    return _HostApp()


@pytest.mark.asyncio
async def test_message_input_queues_prompt_and_shows_queued_bubble(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    storage = Storage(tmp_path / "history.db")
    q = storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa", launch_flags=["--model", "haiku"])
    app = await _open(storage)
    async with app.run_test() as pilot:
        await pilot.pause()
        box = app.screen.query_one("#message-input", Input)
        box.focus()
        await pilot.press(*"ahoj")
        await pilot.press("enter")
        await pilot.pause()
        assert [i.prompt_text for i in storage.list_pending_items(q.id)] == ["ahoj"]
        assert box.value == ""
        queued = app.screen.query(".message-box-queued")
        assert len(queued) == 1 and "ahoj" in str(queued.first().render())
        assert "1 queued" in str(app.screen.query_one("#conversation-status").render())
        assert "Haiku" in str(app.screen.query_one("#conversation-header").render())


@pytest.mark.asyncio
async def test_new_queue_appears_and_select_queue_id_opens_it(tmp_path, monkeypatch):
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    storage = Storage(tmp_path / "history.db")
    storage.create_queue("a", "/tmp/a", "s-a")
    b = storage.create_queue("b", "/tmp/b", "s-b")
    app = await _open(storage, select_queue_id=b.id)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen._current_queue_id == b.id
        storage.create_queue("c", "/tmp/c", "s-c")
        await app.screen._refresh_current()
        await pilot.pause()
        table = app.screen.query_one("#conversation-queue-list", DataTable)
        assert table.row_count == 3
        assert app.screen._current_queue_id == b.id


@pytest.mark.asyncio
async def test_status_line_shows_waiting_for_reset(tmp_path, monkeypatch):
    from datetime import datetime
    from cc_continue.models import QueueStatus
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    storage = Storage(tmp_path / "history.db")
    q = storage.create_queue("a", "/tmp/a", "s-a")
    storage.update_queue_status(q.id, QueueStatus.WAITING_RETRY, next_retry_at=datetime(2026, 10, 12, 15, 0))
    app = await _open(storage)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "15:00" in str(app.screen.query_one("#conversation-status").render())


@pytest.mark.asyncio
async def test_truncated_tool_preview_with_bracket_does_not_crash(tmp_path, monkeypatch):
    # Regression: a tool-call preview is cut at 80 chars, which can leave
    # an unclosed `[data-section=\"quick…` — Textual's markup parser raised
    # MarkupError on it even after rich's escape(), crashing the screen.
    # Real text from a captured transcript.
    monkeypatch.setattr("cc_continue.transcript.PROJECTS_ROOT", tmp_path / "projects")
    project_dir = tmp_path / "projects" / "-tmp-proj-a"
    project_dir.mkdir(parents=True)
    storage = Storage(tmp_path / "history.db")
    storage.create_queue("proj-a", "/tmp/proj-a", "session-aaa")
    script = "(() => {\n  const el = document.querySelector('[data-section=\"quick-actions\"]'); return el; })()"
    (project_dir / "session-aaa.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "name": "browser_eval", "input": {"script": script}}]},
                "timestamp": "2026-09-04T10:00:00.000Z",
            }
        )
        + "\n"
    )
    app = await _open(storage)
    async with app.run_test() as pilot:
        await pilot.pause()
        text = "\n".join(str(s.render()) for s in app.screen.query("#conversation-transcript Static"))
        assert "data-section" in text
