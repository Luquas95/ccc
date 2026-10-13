"""Telegram notifications from the daemon (queue finished, needs you,
error, usage limit / reset). Configured with `ccc config telegram-token`
and `ccc config telegram-chat`; without both nothing is sent.

The bot token is a secret: it's only ever put into the request URL, never
into a log message or an exception text we log."""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from typing import Callable

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN_KEY = "telegram_token"
TELEGRAM_CHAT_KEY = "telegram_chat"
TELEGRAM_MAX_CHARS = 4096

Sender = Callable[[str, str, str], None]


def send_telegram(token: str, chat_id: str, text: str) -> None:
    body = json.dumps({"chat_id": chat_id, "text": text[:TELEGRAM_MAX_CHARS], "disable_web_page_preview": True})
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


class Notifier:
    def __init__(self, storage, sender: Sender | None = None):
        self.storage = storage
        # None = the module's send_telegram, looked up at send time.
        self.sender = sender
        self._tasks: set[asyncio.Task] = set()

    def _config(self) -> tuple[str, str] | None:
        token = self.storage.get_setting(TELEGRAM_TOKEN_KEY)
        chat = self.storage.get_setting(TELEGRAM_CHAT_KEY)
        return (token, chat) if token and chat else None

    def configured(self) -> bool:
        return self._config() is not None

    def send_now(self, text: str) -> bool:
        config = self._config()
        if config is None:
            return False
        try:
            (self.sender or send_telegram)(config[0], config[1], text)
            return True
        except Exception as exc:  # network down, bad token, ...
            # Only the exception type: its text may contain the URL (token).
            logger.warning("Telegram notification failed (%s)", type(exc).__name__)
            return False

    def notify(self, text: str) -> None:
        """Fire and forget from the daemon's event loop; never blocks it."""
        if not self.configured():
            return
        task = asyncio.get_running_loop().create_task(asyncio.to_thread(self.send_now, text))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
