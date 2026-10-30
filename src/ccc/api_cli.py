"""`ccc api …` — the HTTP API for the Android app (ccc.api): run it, make
the token the app needs, list the devices signed in and sign one out."""
from __future__ import annotations

import argparse
import logging

from ccc import api
from ccc.i18n import _


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("api", help=_("HTTP API for the Android app (serve, token, devices)"))
    sub = parser.add_subparsers(dest="api_command", required=True)
    serve = sub.add_parser("serve", help=_("Run the API (what the ccc-api service runs)"))
    serve.add_argument("--host", default=api.DEFAULT_HOST,
                       help=_("address to listen on (default {host}: reach it through tailscale serve)").format(
                           host=api.DEFAULT_HOST))
    serve.add_argument("--port", type=int, default=api.DEFAULT_PORT)
    token = sub.add_parser("token", help=_("Make the token the app signs in with (shown once)"))
    token.add_argument("--new", action="store_true", help=_("make a new one; every device is signed out"))
    sub.add_parser("devices", help=_("List the devices signed in"))
    revoke = sub.add_parser("revoke", help=_("Sign a device out"))
    revoke.add_argument("id", type=int, help=_("its number from `ccc api devices`"))


def run(storage, db_path: str, args: argparse.Namespace) -> int:
    if args.api_command == "serve":
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        api.serve(db_path, args.host, args.port)
        return 0
    if args.api_command == "devices":
        devices = storage.list_devices()
        for device in devices:
            seen = device.last_seen_at.strftime("%Y-%m-%d %H:%M") if device.last_seen_at else _("never")
            print(f"{device.id:>3}  {device.name}  ·  {_('last seen')} {seen}  {device.last_ip}".rstrip())
        if not devices:
            print(_("No device is signed in."))
        return 0
    if args.api_command == "revoke":
        if not storage.delete_device(args.id):
            print(_("No such device."))
            return 1
        print(_("Signed out."))
        return 0
    if api.has_token(storage) and not args.new:
        print(_("A token is set. ccc keeps only its fingerprint, so it can't show it again — "
                "`ccc api token --new` makes a new one (every device is signed out)."))
        return 0
    print(api.new_token(storage))
    print(_("Enter it in the app now — it isn't shown again. Every token made before no longer works."))
    return 0
