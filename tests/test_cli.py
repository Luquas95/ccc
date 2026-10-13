from ccc.cli import add_command
from ccc.storage import Storage


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


def test_config_continue_text_set_and_show(tmp_path, monkeypatch, capsys):
    from ccc import cli
    from ccc.orchestrator import DEFAULT_CONTINUE_TEXT

    db_path = tmp_path / "history.db"
    monkeypatch.setattr(cli, "default_db_path", lambda: db_path)
    cli.main(["config", "continue-text"])
    assert capsys.readouterr().out.strip() == DEFAULT_CONTINUE_TEXT
    cli.main(["config", "continue-text", "Jedeme dál."])
    assert Storage(db_path).get_setting("continue_text") == "Jedeme dál."
    cli.main(["config", "continue-text"])
    assert capsys.readouterr().out.strip().endswith("Jedeme dál.")


def test_default_db_path_moves_data_from_old_name(tmp_path, monkeypatch):
    from ccc import cli

    monkeypatch.setattr(cli.Path, "home", lambda: tmp_path)
    old = tmp_path / ".local" / "share" / "cc-continue"
    old.mkdir(parents=True)
    (old / "history.db").write_text("db")
    path = cli.default_db_path()
    assert path == tmp_path / ".local" / "share" / "ccc" / "history.db"
    assert path.read_text() == "db"
    assert not old.exists()
    assert cli.default_db_path() == path  # second call: nothing to move
