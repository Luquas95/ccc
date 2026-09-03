from cc_continue.cli import add_command
from cc_continue.storage import Storage


def test_add_command_creates_queue_and_item(tmp_path):
    db_path = tmp_path / "history.db"
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    add_command(str(db_path), str(project_dir), "do the thing")

    storage = Storage(db_path)
    queue = storage.get_queue_by_path(str(project_dir))
    assert queue is not None
    item = storage.next_pending_item(queue.id)
    assert item.prompt_text == "do the thing"


def test_add_command_reuses_existing_queue(tmp_path):
    db_path = tmp_path / "history.db"
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    add_command(str(db_path), str(project_dir), "first")
    add_command(str(db_path), str(project_dir), "second")

    storage = Storage(db_path)
    queue = storage.get_queue_by_path(str(project_dir))
    assert len(storage.runs_for_queue(queue.id)) == 0
    first = storage.next_pending_item(queue.id)
    assert first.prompt_text == "first"
