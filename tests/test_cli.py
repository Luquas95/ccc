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


def test_config_usage_reserve(tmp_path, monkeypatch, capsys):
    import pytest as _pytest
    from ccc import cli

    db_path = tmp_path / "history.db"
    monkeypatch.setattr(cli, "default_db_path", lambda: db_path)
    cli.main(["config", "usage-reserve"])
    assert "off" in capsys.readouterr().out
    cli.main(["config", "usage-reserve", "80"])
    assert Storage(db_path).get_setting("usage_reserve") == "80"
    cli.main(["config", "usage-reserve", "off"])
    assert Storage(db_path).get_setting("usage_reserve") is None or Storage(db_path).get_setting("usage_reserve") == ""
    with _pytest.raises(SystemExit):
        cli.main(["config", "usage-reserve", "150"])


def test_config_discord(tmp_path, monkeypatch, capsys):
    import pytest as _pytest
    from ccc import cli
    from ccc.notify import DISCORD_WEBHOOK_KEY

    db_path = tmp_path / "history.db"
    monkeypatch.setattr(cli, "default_db_path", lambda: db_path)
    hook = "https://discord.com/api/webhooks/123/SECRETTOKEN"
    cli.main(["config", "discord-webhook", hook])
    assert Storage(db_path).get_setting(DISCORD_WEBHOOK_KEY) == hook
    capsys.readouterr()
    cli.main(["config", "discord-webhook"])
    out = capsys.readouterr().out
    assert "SECRETTOKEN" not in out and "webhooks/123" in out  # masked

    with _pytest.raises(SystemExit):
        cli.main(["config", "discord-webhook", "https://evil.example/x"])
    assert Storage(db_path).get_setting(DISCORD_WEBHOOK_KEY) == hook

    sent = []
    monkeypatch.setattr("ccc.notify.send_discord", lambda url, text: sent.append(url))
    monkeypatch.setattr("ccc.notify.send_telegram", lambda *a: sent.append("telegram"))
    cli.main(["config", "discord-test"])
    assert sent == [hook]  # only Discord

    cli.main(["config", "discord-webhook", "off"])
    assert Storage(db_path).get_setting(DISCORD_WEBHOOK_KEY) == ""
    with _pytest.raises(SystemExit):
        cli.main(["config", "discord-test"])


def test_analytics_folder_and_archive(tmp_path, monkeypatch, capsys):
    import pytest as _pytest
    from ccc import cli

    db_path = tmp_path / "history.db"
    monkeypatch.setattr(cli, "default_db_path", lambda: db_path)
    with _pytest.raises(SystemExit):
        cli.main(["archive-analytics"])  # off until a folder is set
    assert not (tmp_path / "analytics").exists()
    out = tmp_path / "vault"
    cli.main(["config", "analytics-folder", str(out)])
    cli.main(["archive-analytics"])
    assert (out / "ccc_analytics.md").exists()
    cli.main(["config", "analytics-folder", "off"])
    capsys.readouterr()
    cli.main(["config", "analytics-folder"])
    assert "(off)" in capsys.readouterr().out


def test_plain_ccc_attaches_to_the_one_instance(monkeypatch):
    from ccc import cli, instance

    calls = []
    monkeypatch.setattr(instance, "attach", lambda: calls.append("attach"))
    monkeypatch.setattr("ccc.tui.app.run_app", lambda db: calls.append("tui"))
    cli.main([])
    assert calls == ["attach"]


def test_ccc_tui_and_ccc_inside_its_own_tmux_run_the_tui(monkeypatch, tmp_path):
    from ccc import cli, instance

    calls = []
    monkeypatch.setattr(instance, "attach", lambda: calls.append("attach"))
    monkeypatch.setattr("ccc.tui.app.run_app", lambda db: calls.append("tui"))
    monkeypatch.setattr(cli, "default_db_path", lambda: tmp_path / "h.db")
    cli.main(["tui"])
    # The service's own loop (even an old one running plain `ccc`) must
    # never attach to itself.
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/ccc,123,0")
    cli.main([])
    assert calls == ["tui", "tui"]


def test_ccc_preset_types_into_claude_or_reports(monkeypatch, tmp_path, capsys):
    import pytest as _pytest

    from ccc import cli

    monkeypatch.setattr(cli, "default_db_path", lambda: tmp_path / "h.db")
    calls, told = [], []
    monkeypatch.setattr("ccc.cli_input.apply_preset", lambda storage, q, n: calls.append((q, n)) or None)
    monkeypatch.setattr(cli, "_tell_tmux_client", lambda client, msg, socket=None: told.append((client, msg)))
    cli.main(["preset", "2", "--queue", "7", "--client", "/dev/pts/3"])
    assert calls == [(7, 2)] and told == []
    monkeypatch.setattr("ccc.cli_input.apply_preset", lambda storage, q, n: "No preset on Alt+2")
    with _pytest.raises(SystemExit):
        cli.main(["preset", "2", "--queue", "7", "--client", "/dev/pts/3"])
    assert told == [("/dev/pts/3", "No preset on Alt+2")]
