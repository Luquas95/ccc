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


def test_config_telegram(tmp_path, monkeypatch, capsys):
    from ccc import cli
    from ccc.notify import TELEGRAM_CHAT_KEY, TELEGRAM_TOKEN_KEY

    db_path = tmp_path / "history.db"
    monkeypatch.setattr(cli, "default_db_path", lambda: db_path)
    cli.main(["config", "telegram-token", "123456:ABCDEFSECRET"])
    cli.main(["config", "telegram-chat", "987"])
    storage = Storage(db_path)
    assert storage.get_setting(TELEGRAM_TOKEN_KEY) == "123456:ABCDEFSECRET"
    assert storage.get_setting(TELEGRAM_CHAT_KEY) == "987"
    capsys.readouterr()
    cli.main(["config", "telegram-token"])
    out = capsys.readouterr().out
    assert "SECRET" not in out and "1234" in out  # masked

    sent = []
    monkeypatch.setattr("ccc.notify.send_telegram", lambda token, chat, text: sent.append((chat, text)))
    cli.main(["config", "telegram-test"])
    assert sent and sent[0][0] == "987"
    assert "sent" in capsys.readouterr().out.lower()


def test_config_telegram_test_without_config_fails(tmp_path, monkeypatch, capsys):
    import pytest as _pytest
    from ccc import cli

    monkeypatch.setattr(cli, "default_db_path", lambda: tmp_path / "history.db")
    with _pytest.raises(SystemExit):
        cli.main(["config", "telegram-test"])
    assert "telegram-token" in capsys.readouterr().err
