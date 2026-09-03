from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from cc_continue.storage import Storage


def default_db_path() -> Path:
    path = Path.home() / ".local" / "share" / "cc-continue" / "history.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def add_command(db_path: str, project_path: str, prompt: str) -> None:
    storage = Storage(db_path)
    queue = storage.get_queue_by_path(project_path)
    if queue is None:
        queue = storage.create_queue(
            Path(project_path).name or project_path, project_path, str(uuid.uuid4())
        )
    storage.add_queue_item(queue.id, prompt)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cc-continue")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Queue a prompt for a project without opening the TUI")
    add_parser.add_argument("project_path")
    add_parser.add_argument("prompt")

    args = parser.parse_args(argv)

    if args.command == "add":
        add_command(str(default_db_path()), str(Path(args.project_path).resolve()), args.prompt)
        return

    from cc_continue.tui.app import run_app

    run_app(str(default_db_path()))


if __name__ == "__main__":
    sys.exit(main())
