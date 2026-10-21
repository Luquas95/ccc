"""`ccc api …` — the HTTP API for the Android app (ccc.api): run it, and
show / renew the token the app needs."""
from __future__ import annotations

import argparse
import logging

from ccc import api
from ccc.i18n import _


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("api", help=_("HTTP API for the Android app (serve, token)"))
    sub = parser.add_subparsers(dest="api_command", required=True)
    serve = sub.add_parser("serve", help=_("Run the API (what the ccc-api service runs)"))
    serve.add_argument("--host", default=api.DEFAULT_HOST,
                       help=_("address to listen on (default {host}: reach it through tailscale serve)").format(
                           host=api.DEFAULT_HOST))
    serve.add_argument("--port", type=int, default=api.DEFAULT_PORT)
    token = sub.add_parser("token", help=_("Make the token the app signs in with (shown once)"))
    token.add_argument("--new", action="store_true", help=_("make a new one; the old one stops working"))


def run(storage, db_path: str, args: argparse.Namespace) -> int:
    if args.api_command == "serve":
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        api.serve(db_path, args.host, args.port)
        return 0
    if api.has_token(storage) and not args.new:
        print(_("A token is set. ccc keeps only its fingerprint, so it can't show it again — "
                "`ccc api token --new` makes a new one (the old one stops working)."))
        return 0
    print(api.new_token(storage))
    print(_("Enter it in the app now — it isn't shown again. A token made before no longer works."))
    return 0
