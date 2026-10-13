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
