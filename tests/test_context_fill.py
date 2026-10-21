import json
from types import SimpleNamespace

import pytest
from textual.app import App
from textual.widgets import DataTable

from ccc import context_fill
from ccc.context_fill import ContextFill, ContextTracker, header_text, list_text, window_for
from ccc.daemon import context_tick
from ccc.storage import Storage


def _reply(tokens=(100, 50_000, 10_000), model="claude-opus-5-5", sidechain=False):
    return json.dumps({
        "type": "assistant", "isSidechain": sidechain, "timestamp": "2026-10-21T10:00:00Z",
        "message": {"id": "m", "model": model, "usage": {
            "input_tokens": tokens[0], "output_tokens": 999,
            "cache_read_input_tokens": tokens[1], "cache_creation_input_tokens": tokens[2]}},
    }) + "\n"


def _queue(session="sess", flags=None, queue_id=1):
    return SimpleNamespace(id=queue_id, session_id=session, launch_flags=flags, archived=False, name="q")


@pytest.fixture
def projects(tmp_path):
    root = tmp_path / "projects"
    (root / "-proj").mkdir(parents=True)
    return root


def test_fill_is_the_last_main_reply_prompt_over_the_window(projects):
    f = projects / "-proj" / "sess.jsonl"
    f.write_text(_reply((1, 1, 1)) + _reply((100, 100_000, 23_900))
                 + _reply((5, 5, 5), sidechain=True)  # a subagent's reply isn't this conversation's context
                 + _reply((7, 7, 7), model="<synthetic>") + '{"type": "user"}\n')
    fill = ContextTracker(projects).fill(_queue())
    assert fill == ContextFill(124_000, 200_000)
    assert fill.percent == 62
    assert list_text(fill) == "62%"
    assert header_text(fill) == "context 62 % · 124k / 200k"


def test_reads_only_new_lines_and_waits_for_a_whole_line(projects):
    f = projects / "-proj" / "sess.jsonl"
    f.write_text(_reply((0, 20_000, 0)))
    tracker = ContextTracker(projects)
    assert tracker.fill(_queue()).tokens == 20_000
    line = _reply((0, 40_000, 0))
    with f.open("a") as fh:
        fh.write(line[:30])
    assert tracker.fill(_queue()).tokens == 20_000  # incomplete line left for later
    with f.open("a") as fh:
        fh.write(line[30:])
    assert tracker.fill(_queue()).tokens == 40_000
    f.write_text(_reply((0, 1000, 0)))  # replaced by a shorter file: read again
    assert tracker.fill(_queue()).tokens == 1000


def test_no_transcript_or_no_reply_yet_shows_nothing(projects):
    assert ContextTracker(projects).fill(_queue()) is None
    (projects / "-proj" / "sess.jsonl").write_text('{"type": "user"}\n')
    assert ContextTracker(projects).fill(_queue()) is None


def test_window_is_known_or_not_guessed():
    assert window_for("claude-sonnet-5-5", None, 10, None) == 200_000
    assert window_for("claude-opus-5-5", ["--model", "opus[1m]"], 10, None) == 1_000_000
    assert window_for("claude-opus-5-5", ["--model=sonnet[1M]"], 10, None) == 1_000_000
    # a prompt past 200k only fits a 1M window
    assert window_for("claude-opus-5-5", None, 437_000, None) == 1_000_000
    assert window_for("claude-opus-5-5", None, 10, 1_000_000) == 1_000_000  # Settings
    assert window_for("gpt-x", None, 10, None) is None
    assert window_for(None, None, 10, None) is None


def test_unknown_model_shows_tokens_without_percent(projects):
    (projects / "-proj" / "sess.jsonl").write_text(_reply((0, 1_234_567, 0), model="some-proxy-model"))
    fill = ContextTracker(projects).fill(_queue())
    # past 200k: deduced 1M even for an unknown name — but below it, nothing is invented
    assert fill.window == 1_000_000
    (projects / "-proj" / "other.jsonl").write_text(_reply((0, 90_000, 0), model="some-proxy-model"))
    fill = ContextTracker(projects).fill(_queue("other"))
    assert fill.percent is None
    assert list_text(fill) == "90k"
    assert header_text(fill) == "context 90k tokens (window unknown)"


def test_short_tokens():
    assert [context_fill.short_tokens(n) for n in (950, 124_400, 200_000, 1_000_000, 1_250_000)] == \
        ["950", "124k", "200k", "1M", "1.2M"]


def test_levels_follow_the_thresholds(tmp_path):
    storage = Storage(tmp_path / "h.db")
    assert context_fill.thresholds(storage) == (80, 90)
    storage.set_setting(context_fill.WARN_KEY, "70")
    storage.set_setting(context_fill.DANGER_KEY, "85")
    warn, danger = context_fill.thresholds(storage)
    assert context_fill.level(ContextFill(130_000, 200_000), warn, danger) == ""
    assert context_fill.level(ContextFill(140_000, 200_000), warn, danger) == "warn"
    assert context_fill.level(ContextFill(170_000, 200_000), warn, danger) == "danger"
    assert context_fill.level(ContextFill(999_000, None), warn, danger) == ""


def test_alerts_once_and_again_after_dropping_below(tmp_path):
    storage = Storage(tmp_path / "h.db")
    full, empty = ContextFill(170_000, 200_000), ContextFill(10_000, 200_000)
    assert context_fill.alerts(storage, {1: full, 2: empty}) == [1]
    assert context_fill.alerts(storage, {1: full}) == []  # kept across restarts (in the settings)
    assert context_fill.alerts(storage, {1: empty}) == []  # /compact
    assert context_fill.alerts(storage, {1: full}) == [1]


class _Notifier:
    def __init__(self, configured=True):
        self._configured, self.sent = configured, []

    def configured(self):
        return self._configured

    def send_now(self, text):
        self.sent.append(text)
        return True


def test_daemon_notifies_when_a_conversation_reaches_the_warning(tmp_path, projects):
    storage = Storage(tmp_path / "h.db")
    q = storage.create_queue("shop-api", "/tmp/a", "sess")
    (projects / "-proj" / "sess.jsonl").write_text(_reply((0, 170_000, 0)))
    tracker = ContextTracker(projects)
    notifier = _Notifier()
    assert context_tick(storage, notifier, tracker) == notifier.sent
    assert len(notifier.sent) == 1 and "shop-api" in notifier.sent[0] and "85 %" in notifier.sent[0]
    context_tick(storage, notifier, tracker)
    assert len(notifier.sent) == 1  # once
    storage.set_setting(context_fill.ALERTED_KEY, "")
    storage.set_setting(context_fill.NOTIFY_KEY, "off")
    assert context_tick(storage, notifier, tracker) == []
    storage.set_setting(context_fill.NOTIFY_KEY, "")
    assert context_tick(storage, _Notifier(configured=False), tracker) == []
    assert q.id not in context_fill._alerted(storage)  # not used up while nothing could be sent


@pytest.mark.asyncio
async def test_conversations_show_the_fill_in_the_list_and_header(tmp_path, monkeypatch, projects):
    from ccc.tui.conversations import ConversationsScreen

    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", projects)
    storage = Storage(tmp_path / "h.db")
    storage.create_queue("calm", "/tmp/a", "s-calm")
    storage.create_queue("full", "/tmp/b", "s-full")
    (projects / "-proj" / "s-calm.jsonl").write_text(_reply((0, 124_000, 0)))
    (projects / "-proj" / "s-full.jsonl").write_text(_reply((0, 185_000, 0)))
    screen = ConversationsScreen(storage)

    class _HostApp(App):
        async def on_mount(self):
            await self.push_screen(screen)

    app = _HostApp()
    async with app.run_test(size=(160, 40)) as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await screen._refresh_current()
        await pilot.pause()
        table = screen.query_one("#conversation-queue-list", DataTable)
        rows = [table.get_row_at(n)[0] for n in range(table.row_count)]
        by_name = {name: next(r for r in rows if name in r.plain) for name in ("calm", "full")}
        assert by_name["calm"].plain.endswith("62%")
        assert by_name["full"].plain.endswith("92%")
        assert any("red" in str(span.style) for span in by_name["full"].spans)
        screen._current_queue_id = next(q.id for q in storage.list_queues() if q.name == "full")
        await screen._refresh_current()
        header = str(screen.query_one("#conversation-header").render())
        assert "context 92 % · 185k / 200k" in header
        assert "consider /compact or a new conversation" in header
