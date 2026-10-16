import asyncio
import json

import pytest

from ccc.notify import TELEGRAM_CHAT_KEY, TELEGRAM_TOKEN_KEY, Notifier, send_telegram
from ccc.storage import Storage


def test_notifier_does_nothing_without_config(tmp_path):
    sent = []
    notifier = Notifier(Storage(tmp_path / "h.db"), sender=lambda *a: sent.append(a))
    assert notifier.configured() is False
    assert notifier.send_now("hi") is False
    assert sent == []


def test_notifier_sends_with_config(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.set_setting(TELEGRAM_TOKEN_KEY, "123:abc")
    storage.set_setting(TELEGRAM_CHAT_KEY, "42")
    sent = []
    notifier = Notifier(storage, sender=lambda token, chat, text: sent.append((token, chat, text)))
    assert notifier.send_now("hi") is True
    assert sent == [("123:abc", "42", "hi")]


def test_sender_errors_are_swallowed_and_token_not_logged(tmp_path, caplog):
    storage = Storage(tmp_path / "h.db")
    storage.set_setting(TELEGRAM_TOKEN_KEY, "123:SECRET")
    storage.set_setting(TELEGRAM_CHAT_KEY, "42")

    def boom(token, chat, text):
        raise OSError(f"failed for https://api.telegram.org/bot{token}/sendMessage")

    assert Notifier(storage, sender=boom).send_now("hi") is False
    assert "SECRET" not in caplog.text and "Telegram" in caplog.text


def test_send_telegram_builds_request(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setattr("ccc.notify.urllib.request.urlopen", fake_urlopen)
    send_telegram("1:t", "99", "x" * 5000)
    assert captured["url"] == "https://api.telegram.org/bot1:t/sendMessage"
    assert captured["body"]["chat_id"] == "99"
    assert len(captured["body"]["text"]) <= 4096


async def test_notify_runs_in_background(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.set_setting(TELEGRAM_TOKEN_KEY, "t")
    storage.set_setting(TELEGRAM_CHAT_KEY, "c")
    sent = []
    notifier = Notifier(storage, sender=lambda *a: sent.append(a[2]))
    notifier.notify("bg")
    await notifier.drain()
    assert sent == ["bg"]


# --- Discord ----------------------------------------------------------------

from ccc.notify import DISCORD_WEBHOOK_KEY, is_discord_webhook, send_discord  # noqa: E402

HOOK = "https://discord.com/api/webhooks/123/SECRETTOKEN"


def test_is_discord_webhook():
    assert is_discord_webhook(HOOK)
    assert is_discord_webhook("https://discordapp.com/api/webhooks/1/x")
    assert is_discord_webhook("https://canary.discord.com/api/webhooks/1/x")
    assert not is_discord_webhook("http://discord.com/api/webhooks/1/x")
    assert not is_discord_webhook("https://evil.example/api/webhooks/1/x")
    assert not is_discord_webhook("https://discord.com.evil.example/api/webhooks/1/x")
    assert not is_discord_webhook("")


def test_send_discord_builds_request(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b""

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["ua"] = request.get_header("User-agent")
        return FakeResponse()

    monkeypatch.setattr("ccc.notify.urllib.request.urlopen", fake_urlopen)
    send_discord(HOOK, "x" * 3000)
    assert captured["url"] == HOOK
    assert len(captured["body"]["content"]) <= 2000
    assert captured["body"]["allowed_mentions"] == {"parse": []}
    assert captured["ua"] and "Python-urllib" not in captured["ua"]


def test_discord_only_is_configured_and_sends(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.set_setting(DISCORD_WEBHOOK_KEY, HOOK)
    sent = []
    notifier = Notifier(storage, sender=lambda *a: sent.append("tg"), discord_sender=lambda url, text: sent.append((url, text)))
    assert notifier.configured()
    assert notifier.send_now("hi") is True
    assert sent == [(HOOK, "hi")]


def test_both_channels_and_one_failing(tmp_path, caplog):
    storage = Storage(tmp_path / "h.db")
    storage.set_setting(TELEGRAM_TOKEN_KEY, "t")
    storage.set_setting(TELEGRAM_CHAT_KEY, "c")
    storage.set_setting(DISCORD_WEBHOOK_KEY, HOOK)
    sent = []

    def discord_boom(url, text):
        raise OSError(f"failed for {url}")

    notifier = Notifier(storage, sender=lambda t, c, text: sent.append(text), discord_sender=discord_boom)
    assert notifier.send_now("hi") is True  # Telegram still got it
    assert sent == ["hi"]
    assert "SECRETTOKEN" not in caplog.text and "Discord" in caplog.text


def test_invalid_stored_webhook_is_ignored(tmp_path):
    storage = Storage(tmp_path / "h.db")
    storage.set_setting(DISCORD_WEBHOOK_KEY, "https://evil.example/x")
    notifier = Notifier(storage, discord_sender=lambda *a: pytest.fail("must not send"))
    assert not notifier.configured()
    assert notifier.send_now("hi") is False


# --- files (exports) ----------------------------------------------------------

from email import message_from_bytes  # noqa: E402
from email.policy import HTTP  # noqa: E402

from ccc.notify import send_discord_file, send_telegram_file  # noqa: E402


def _capture_multipart(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["ua"] = request.get_header("User-agent")
        raw = f"Content-Type: {request.get_header('Content-type')}\r\n\r\n".encode() + request.data
        parts = message_from_bytes(raw, policy=HTTP).iter_parts()
        captured["parts"] = {p.get_param("name", header="content-disposition"): p for p in parts}
        return FakeResponse()

    monkeypatch.setattr("ccc.notify.urllib.request.urlopen", fake_urlopen)
    return captured


def test_send_telegram_file_uploads_document(monkeypatch, tmp_path):
    captured = _capture_multipart(monkeypatch)
    path = tmp_path / "chat-1.md"
    path.write_text("# Ahoj\nžluťoučký kůň")
    send_telegram_file("1:t", "99", path, "c" * 2000)
    assert captured["url"] == "https://api.telegram.org/bot1:t/sendDocument"
    parts = captured["parts"]
    assert parts["chat_id"].get_content().strip() == "99"
    assert len(parts["caption"].get_content().strip()) <= 1024
    assert parts["document"].get_filename() == "chat-1.md"
    assert parts["document"].get_payload(decode=True) == path.read_bytes()


def test_send_discord_file_uploads_attachment(monkeypatch, tmp_path):
    captured = _capture_multipart(monkeypatch)
    path = tmp_path / "shot.svg"
    path.write_text("<svg/>")
    send_discord_file(HOOK, path, "ccc: shot.svg @everyone")
    parts = captured["parts"]
    payload = json.loads(parts["payload_json"].get_content())
    assert payload["content"] == "ccc: shot.svg @everyone"
    assert payload["allowed_mentions"] == {"parse": []}
    assert parts["files[0]"].get_filename() == "shot.svg"
    assert parts["files[0]"].get_payload(decode=True) == b"<svg/>"
    assert captured["ua"] and "Python-urllib" not in captured["ua"]


def test_file_sending_needs_config_and_respects_size(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr("ccc.notify.send_telegram_file", lambda *a: sent.append(a))
    storage = Storage(tmp_path / "h.db")
    path = tmp_path / "x.md"
    path.write_text("x")
    notifier = Notifier(storage)
    assert notifier.send_file_telegram_now(path, "c") is False  # not set up
    storage.set_setting(TELEGRAM_TOKEN_KEY, "t")
    storage.set_setting(TELEGRAM_CHAT_KEY, "c")
    assert notifier.send_file_telegram_now(path, "c") is True
    monkeypatch.setattr("ccc.notify.TELEGRAM_MAX_FILE_BYTES", 0)
    assert notifier.send_file_telegram_now(path, "c") is False
    assert len(sent) == 1


def test_file_sending_failure_never_logs_the_secret(monkeypatch, tmp_path, caplog):
    def boom(url, path, text):
        raise RuntimeError(f"failed {url}")

    monkeypatch.setattr("ccc.notify.send_discord_file", boom)
    storage = Storage(tmp_path / "h.db")
    storage.set_setting(DISCORD_WEBHOOK_KEY, HOOK)
    path = tmp_path / "x.md"
    path.write_text("x")
    assert Notifier(storage).send_file_discord_now(path, "c") is False
    assert HOOK not in caplog.text and "Discord" in caplog.text
