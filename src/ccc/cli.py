from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ccc.orchestrator import enqueue_prompt
from ccc.storage import Storage


# Data directory used before the project was renamed from cc-continue.
OLD_DATA_DIR_NAME = "cc-continue"


def default_db_path() -> Path:
    data_dir = Path.home() / ".local" / "share" / "ccc"
    old_dir = data_dir.parent / OLD_DATA_DIR_NAME
    if old_dir.is_dir() and not data_dir.exists():
        old_dir.rename(data_dir)  # carry history over from the old name
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "history.db"


def add_command(db_path: str, project_path: str, prompt: str) -> None:
    storage = Storage(db_path)
    enqueue_prompt(storage, project_path, prompt)


def config_command(db_path: str, setting: str, value: str | None) -> None:
    from ccc.orchestrator import DEFAULT_CONTINUE_TEXT

    from ccc.notify import TELEGRAM_CHAT_KEY, TELEGRAM_TOKEN_KEY, Notifier

    storage = Storage(db_path)
    if setting == "telegram-test":
        notifier = Notifier(storage)
        if not notifier.configured():
            print("ccc: set `ccc config telegram-token …` and `ccc config telegram-chat …` first", file=sys.stderr)
            sys.exit(1)
        if notifier.send_now("✅ ccc: Telegram notifications work."):
            print("Test message sent.")
        else:
            print("ccc: sending failed — check the token and chat id", file=sys.stderr)
            sys.exit(1)
        return
    if setting in ("telegram-token", "telegram-chat"):
        key = TELEGRAM_TOKEN_KEY if setting == "telegram-token" else TELEGRAM_CHAT_KEY
        if value is None:
            current = storage.get_setting(key)
            if current and setting == "telegram-token":
                current = current[:4] + "…" + current[-2:]  # never print the secret
            print(current or "(not set)")
        else:
            storage.set_setting(key, value.strip())
            print(f"{setting} saved.")
        return
    if setting == "usage-reserve":
        from ccc.orchestrator import RESERVE_KEY, usage_reserve

        if value is None:
            current = usage_reserve(storage)
            print(f"{current}%" if current else "off")
            return
        if value.strip().lower() in ("off", "0", "none"):
            storage.set_setting(RESERVE_KEY, "")
            print("usage-reserve off.")
            return
        try:
            percent = int(value.strip().rstrip("%"))
        except ValueError:
            percent = -1
        if not 0 < percent < 100:
            print("ccc: usage-reserve takes a number from 1 to 99, or off", file=sys.stderr)
            sys.exit(1)
        storage.set_setting(RESERVE_KEY, str(percent))
        print(f"usage-reserve set to {percent}%: queued tasks wait while a usage window is at or above it.")
        return
    if setting == "continue-text":
        if value is None:
            print(storage.get_setting("continue_text", DEFAULT_CONTINUE_TEXT))
        else:
            storage.set_setting("continue_text", value)
            print(f"continue-text set to: {value}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ccc")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser(
        "add",
        help="Queue a prompt for a project without opening the TUI "
        "(needs ccc-daemon running to actually execute it)",
    )
    add_parser.add_argument("project_path")
    add_parser.add_argument("prompt")

    subparsers.add_parser("backup", help="Back up the ccc database now (the daemon also does it daily)")

    config_parser = subparsers.add_parser("config", help="Show or change ccc settings")
    config_sub = config_parser.add_subparsers(dest="setting", required=True)
    continue_parser = config_sub.add_parser(
        "continue-text",
        help="Message sent after a usage limit interrupted a prompt mid-way (no value: show it)",
    )
    continue_parser.add_argument("value", nargs="?")
    token_parser = config_sub.add_parser("telegram-token", help="Telegram bot token for notifications (no value: show it masked)")
    token_parser.add_argument("value", nargs="?")
    chat_parser = config_sub.add_parser("telegram-chat", help="Telegram chat id to notify (no value: show it)")
    chat_parser.add_argument("value", nargs="?")
    reserve_parser = config_sub.add_parser(
        "usage-reserve", help="Don't start queued tasks above this % of a usage window (1-99, or off)"
    )
    reserve_parser.add_argument("value", nargs="?")
    test_parser = config_sub.add_parser("telegram-test", help="Send a test notification")
    test_parser.set_defaults(value=None)

    args = parser.parse_args(argv)

    if args.command == "backup":
        from ccc import backup

        db_path = default_db_path()
        path = backup.backup_now(db_path, backup.default_backup_dir(db_path))
        backup.prune(path.parent)
        print(f"Backed up to {path}")
        return

    if args.command == "config":
        config_command(str(default_db_path()), args.setting, args.value)
        return

    if args.command == "add":
        try:
            add_command(str(default_db_path()), str(Path(args.project_path).resolve()), args.prompt)
        except ValueError as exc:
            print(f"ccc add: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    from ccc.tui.app import run_app

    run_app(str(default_db_path()))


if __name__ == "__main__":
    sys.exit(main())
