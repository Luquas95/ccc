import pytest
from textual.widgets import Button, Checkbox, DataTable, Input, TextArea

from ccc.models import ReviewStatus, Verdict
from ccc.storage import Storage
from ccc.tui.app import CCContinueApp
from ccc.tui.review import ReviewModal


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setattr("ccc.tui.session_picker.discover_sessions", lambda: [])
    monkeypatch.setattr("ccc.tui.analytics.get_pro_usage", lambda: None)
    monkeypatch.setattr("ccc.transcript.PROJECTS_ROOT", tmp_path / "projects")


def _app(tmp_path):
    db_path = tmp_path / "history.db"
    storage = Storage(db_path)
    queue = storage.create_queue("shop", str(tmp_path), "s1")
    return CCContinueApp(str(db_path)), queue


@pytest.mark.asyncio
async def test_v_asks_for_a_review_until_it_passes(tmp_path):
    app, queue = _app(tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.screen.set_focus(None)
        await pilot.press("v")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ReviewModal) and modal.queue_id == queue.id
        modal.query_one("#review-instructions", TextArea).text = "the error paths"
        modal.query_one("#review-until-pass", Checkbox).value = True
        modal.query_one("#review-rounds", Input).value = "3"
        await pilot.press("ctrl+s")
        await pilot.pause()
        [review] = app.storage.list_reviews(queue.id)
        assert (review.instructions, review.until_pass, review.max_rounds, review.status) == \
            ("the error paths", True, 3, ReviewStatus.PENDING)
        assert modal.query_one("#review-start", Button).disabled  # one at a time
        await pilot.click("#review-stop")
        await pilot.pause()
        assert app.storage.get_review(review.id).status == ReviewStatus.STOPPED


@pytest.mark.asyncio
async def test_findings_can_be_sent_to_the_conversation(tmp_path):
    app, queue = _app(tmp_path)
    review = app.storage.add_review(queue.id)
    app.storage.update_review(review.id, status=ReviewStatus.DONE, verdict=Verdict.FAIL,
                              report="auth.py:12 accepts expired tokens\nVERDICT: FAIL — auth.py:12")
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        app.push_screen(ReviewModal(app.storage, queue.id))
        await pilot.pause()
        modal = app.screen
        assert modal.query_one("#review-table", DataTable).row_count == 1
        assert not modal.query_one("#review-apply", Button).disabled
        await pilot.click("#review-apply")
        await pilot.pause()
        [item] = app.storage.list_pending_items(queue.id)
        assert "auth.py:12 accepts expired tokens" in item.prompt_text
        assert modal.query_one("#review-apply", Button).disabled  # sent once
