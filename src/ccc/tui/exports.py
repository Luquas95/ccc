"""After a file is exported (e, Ctrl+T): also send it to Telegram /
Discord when Settings → Exports says so."""
from __future__ import annotations

from pathlib import Path

from textual.app import App

from ccc.export_paths import TELEGRAM, send_targets
from ccc.i18n import _
from ccc.notify import Notifier


def send_export(app: App, storage, path: Path) -> None:
    """Uploads run in a thread so they never freeze the TUI; the result
    shows up as a notification."""
    targets = send_targets(storage)
    if targets:
        app.run_worker(lambda: _send(app, storage, path, targets), thread=True, group="send-export")


def _send(app: App, storage, path: Path, targets: list[str]) -> None:
    notifier = Notifier(storage)
    caption = f"ccc: {path.name}"
    for target in targets:
        name = "Telegram" if target == TELEGRAM else "Discord"
        if target == TELEGRAM:
            sent = notifier.send_file_telegram_now(path, caption)
        else:
            sent = notifier.send_file_discord_now(path, caption)
        if sent:
            app.call_from_thread(app.notify, path.name, title=_("Sent to {target}").format(target=name))
        else:
            app.call_from_thread(
                app.notify,
                _("Check {target} in Settings (Ctrl+P), or the file is too big.").format(target=name),
                title=_("Not sent to {target}").format(target=name),
                severity="warning",
            )
