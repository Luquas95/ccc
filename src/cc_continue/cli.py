from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cc_continue.orchestrator import enqueue_prompt
from cc_continue.storage import Storage


def default_db_path() -> Path:
    path = Path.home() / ".local" / "share" / "cc-continue" / "history.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def add_command(db_path: str, project_path: str, prompt: str) -> None:
    storage = Storage(db_path)
    enqueue_prompt(storage, project_path, prompt)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cc-continue")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser(
        "add",
        help="Queue a prompt for a project without opening the TUI "
        "(needs cc-continue-daemon running to actually execute it)",
    )
    add_parser.add_argument("project_path")
    add_parser.add_argument("prompt")

    args = parser.parse_args(argv)

    if args.command == "add":
        try:
            add_command(str(default_db_path()), str(Path(args.project_path).resolve()), args.prompt)
        except ValueError as exc:
            print(f"cc-continue add: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    from cc_continue.tui.app import run_app

    run_app(str(default_db_path()))


if __name__ == "__main__":
    sys.exit(main())
