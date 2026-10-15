"""Notifications from the daemon (queue finished, needs you, error, usage
limit / reset) to Telegram and/or Discord. Telegram: `ccc config
telegram-token` + `telegram-chat`; Discord: `ccc config discord-webhook`.
Without any of them nothing is sent.

The Telegram bot token and the Discord webhook URL are secrets: they're only
ever put into the request URL, never into a log message or an exception text
we log."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.request
from typing import Callable

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN_KEY = "telegram_token"
TELEGRAM_CHAT_KEY = "telegram_chat"
TELEGRAM_MAX_CHARS = 4096

DISCORD_WEBHOOK_KEY = "discord_webhook"
DISCORD_MAX_CHARS = 2000
# Discord (Cloudflare) rejects urllib's default "Python-urllib/x.y" agent.
USER_AGENT = "ccc-notifier (https://github.com/Luquas95/ccc, 1.0)"
_DISCORD_WEBHOOK_RE = re.compile(r"^https://(?:(?:ptb|canary)\.)?(?:discord|discordapp)\.com/api/webhooks/\S+$")

Sender = Callable[[str, str, str], None]
DiscordSender = Callable[[str, str], None]


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


def is_discord_webhook(url: str) -> bool:
    return bool(_DISCORD_WEBHOOK_RE.match(url or ""))


def send_discord(webhook_url: str, text: str) -> None:
    # No mentions: text quoted from Claude must never ping @everyone.
    body = json.dumps({"content": text[:DISCORD_MAX_CHARS], "allowed_mentions": {"parse": []}})
    request = urllib.request.Request(
        webhook_url,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


class Notifier:
    def __init__(self, storage, sender: Sender | None = None, discord_sender: DiscordSender | None = None):
        self.storage = storage
        # None = the module's send_telegram / send_discord, looked up at send time.
        self.sender = sender
        self.discord_sender = discord_sender
        self._tasks: set[asyncio.Task] = set()

    def _telegram_config(self) -> tuple[str, str] | None:
        token = self.storage.get_setting(TELEGRAM_TOKEN_KEY)
        chat = self.storage.get_setting(TELEGRAM_CHAT_KEY)
        return (token, chat) if token and chat else None

    def _discord_webhook(self) -> str | None:
        url = self.storage.get_setting(DISCORD_WEBHOOK_KEY)
        return url if url and is_discord_webhook(url) else None

    def telegram_configured(self) -> bool:
        return self._telegram_config() is not None

    def discord_configured(self) -> bool:
        return self._discord_webhook() is not None

    def configured(self) -> bool:
        return self.telegram_configured() or self.discord_configured()

    def send_telegram_now(self, text: str) -> bool:
        config = self._telegram_config()
        if config is None:
            return False
        try:
            (self.sender or send_telegram)(config[0], config[1], text)
            return True
        except Exception as exc:  # network down, bad token, ...
            # Only the exception type: its text may contain the URL (token).
            logger.warning("Telegram notification failed (%s)", type(exc).__name__)
            return False

    def send_discord_now(self, text: str) -> bool:
        url = self._discord_webhook()
        if url is None:
            return False
        try:
            (self.discord_sender or send_discord)(url, text)
            return True
        except Exception as exc:
            # Only the exception type: its text may contain the webhook URL.
            logger.warning("Discord notification failed (%s)", type(exc).__name__)
            return False

    def send_now(self, text: str) -> bool:
        """Send to every configured channel; True if at least one got it."""
        telegram = self.send_telegram_now(text)
        discord = self.send_discord_now(text)
        return telegram or discord

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
