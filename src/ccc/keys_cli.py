"""`ccc keys …` — the keyboard shortcuts from the terminal (and scripts):
list them, check a key is free, change, reset, export and import them.
The same checks as Settings → Keyboard shortcuts (keymap.problems): a
key that collides is never saved, and the exit code says so (1)."""
from __future__ import annotations

import argparse

from ccc import keymap
from ccc.i18n import _


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("keys", help=_("Show, check, change, export or import ccc's keyboard shortcuts"))
    sub = parser.add_subparsers(dest="keys_command", required=True)
    sub.add_parser("list", help=_("Every shortcut: action id, key, what it does"))
    check = sub.add_parser("check", help=_("Is a key free? With an action id: free for that action"))
    check.add_argument("key", help=_("e.g. ctrl+o, Alt+S, F5, +"))
    check.add_argument("action", nargs="?", default=None, help=_("action id (see `ccc keys list`)"))
    set_parser = sub.add_parser("set", help=_("Give an action a new key (refused if it collides)"))
    set_parser.add_argument("action")
    set_parser.add_argument("key")
    reset = sub.add_parser("reset", help=_("Back to the default key (one action, or all)"))
    reset.add_argument("action", nargs="?", default=None)
    export = sub.add_parser("export", help=_("Write the shortcuts to FOLDER/ccc-keys.json"))
    export.add_argument("folder")
    imp = sub.add_parser("import", help=_("Use the shortcuts from a ccc-keys.json (or the folder with it)"))
    imp.add_argument("path")


def _action(action_id: str) -> keymap.KeyAction:
    if action_id not in keymap.BY_ID:
        raise SystemExit(_("Unknown action “{action}” — see `ccc keys list`.").format(action=action_id))
    return keymap.BY_ID[action_id]


def _key(text: str) -> str:
    key = keymap.parse(text)
    if key is None:
        raise SystemExit(_("“{key}” isn't a key ccc knows.").format(key=text))
    return key


def _saved() -> None:
    print(_("Saved. The running ccc uses it after a restart (systemctl --user restart ccc-tui)."))


def run(storage, args: argparse.Namespace) -> int:
    keys = keymap.current(storage)
    command = args.keys_command
    if command == "list":
        width = max(len(a.id) for a in keymap.ACTIONS)
        for action in keymap.ACTIONS:
            key = keys[action.id]
            mark = "*" if key != action.default else " "
            print(f"{action.id:<{width}}  {mark}{keymap.pretty(key):<10}  {keymap.label(action)}")
        print(_("* = changed (default: `ccc keys reset ACTION`)"))
        return 0
    if command == "check":
        key = _key(args.key)
        if args.action:
            found = keymap.problems(_action(args.action).id, key, keys)
        else:
            found = _free_anywhere(key, keys)
        if found:
            print("\n".join(found))
            return 1
        print(_("{key} is free.").format(key=keymap.pretty(key)))
        return 0
    if command == "set":
        action = _action(args.action)
        key = _key(args.key)
        found = keymap.problems(action.id, key, keys)
        if found:
            print(_("Not changed:") + " " + " ".join(found))
            return 1
        keymap.save(storage, {**keys, action.id: key})
        _saved()
        return 0
    if command == "reset":
        new = keymap.defaults() if args.action is None else {**keys, _action(args.action).id: keymap.BY_ID[args.action].default}
        try:
            keymap.save(storage, new)
        except keymap.KeymapError as error:
            print(_("Not changed:") + "\n" + str(error))
            return 1
        _saved()
        return 0
    if command == "export":
        try:
            path = keymap.export(keys, args.folder)
        except OSError as error:
            print(_("Export failed: {error}").format(error=error.strerror or error))
            return 1
        print(_("Exported to {path}").format(path=path))
        return 0
    if command == "import":
        try:
            imported = keymap.read_export(args.path)
            keymap.save(storage, imported)
        except keymap.KeymapError as error:
            print(_("Not imported — the shortcuts in it collide:") + "\n" + str(error))
            return 1
        except ValueError as error:
            print(error)
            return 1
        _saved()
        return 0
    return 2


def _free_anywhere(key: str, keys: dict[str, str]) -> list[str]:
    """Without an action: who has the key already, and whether it can be
    used at all (reserved keys)."""
    found = [_("{key} is already “{label}”.").format(key=keymap.pretty(key), label=keymap.label(a))
             for a in keymap.ACTIONS if keys[a.id] == key]
    if key in keymap.RESERVED:
        found.append(_("{key} can't be used: {why}.").format(key=keymap.pretty(key), why=_(keymap.RESERVED[key])))
    if key in keymap.WIDGET_KEYS:
        found.append(_("{key} is used by lists and text fields.").format(key=keymap.pretty(key)))
    if key in keymap.CLAUDE_KEYS:
        found.append(_("{key} is a Claude Code key (fine for keys that only work in ccc, not for "
                       "the ones that work from the Claude Code pane).").format(key=keymap.pretty(key)))
    return found
