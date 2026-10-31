"""`ccc api …` — the HTTP API for the Android app (ccc.api): run it, make
the token the app needs, list the devices signed in and sign one out."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from ccc import api, pairing
from ccc.i18n import _
from ccc.models import REVOKED_BY_COMPUTER, ROLES


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("api", help=_("HTTP API for the Android app (serve, token, pair, devices)"))
    sub = parser.add_subparsers(dest="api_command", required=True)
    serve = sub.add_parser("serve", help=_("Run the API (what the ccc-api service runs)"))
    serve.add_argument("--host", default=api.DEFAULT_HOST,
                       help=_("address to listen on (default {host}: reach it through tailscale serve)").format(
                           host=api.DEFAULT_HOST))
    serve.add_argument("--port", type=int, default=api.DEFAULT_PORT)
    token = sub.add_parser("token", help=_("Make the token the app signs in with (shown once)"))
    token.add_argument("--new", action="store_true", help=_("make a new one; every device is signed out"))
    pair = sub.add_parser("pair", help=_("Show a QR code the app scans to sign in (good for 5 minutes)"))
    pair.add_argument("--server", help=_("the API's address, if ccc can't find it (https://…ts.net)"))
    pair.add_argument("--image", nargs="?", const="", metavar="FILE",
                      help=_("save the QR as a picture (default ~/Pictures/ccc-pair-qr.png) instead of drawing it in the terminal"))
    pair.add_argument("--role", choices=ROLES, default=pairing.DEFAULT_ROLE,
                      help=_("what the phone may do: read (look only), operate (also steer existing conversations; default), "
                             "admin (also start conversations, terminal, updates, settings)"))
    role = sub.add_parser("role", help=_("Change what a device may do"))
    role.add_argument("id", type=int, help=_("its number from `ccc api devices`"))
    role.add_argument("role", choices=ROLES)
    devices = sub.add_parser("devices", help=_("List the devices signed in"))
    devices.add_argument("--all", action="store_true", help=_("also the devices signed out (history, read only)"))
    revoke = sub.add_parser("revoke", help=_("Sign a device out"))
    revoke.add_argument("id", type=int, help=_("its number from `ccc api devices`"))


def run(storage, db_path: str, args: argparse.Namespace) -> int:
    if args.api_command == "serve":
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        api.serve(db_path, args.host, args.port)
        return 0
    if args.api_command == "pair":
        return _pair(storage, args.server, getattr(args, "image", None), getattr(args, "role", pairing.DEFAULT_ROLE))
    if args.api_command == "role":
        if not storage.set_device_role(args.id, args.role):
            print(_("No such device."))
            return 1
        print(_("Role changed to {role}.").format(role=args.role))
        return 0
    if args.api_command == "devices":
        devices = storage.list_devices(include_revoked=args.all)
        for device in devices:
            seen = device.last_seen_at.strftime("%Y-%m-%d %H:%M") if device.last_seen_at else _("never")
            line = f"{device.id:>3}  {device.name} [{device.role}]  ·  {_('last seen')} {seen}  {device.last_ip}".rstrip()
            if device.revoked_at:
                line += f"  ·  {_('signed out')} {device.revoked_at.strftime('%Y-%m-%d %H:%M')} ({api.revoked_label(device)})"
            print(line)
        if not devices:
            print(_("No device is signed in."))
        return 0
    if args.api_command == "revoke":
        if not storage.revoke_device(args.id, REVOKED_BY_COMPUTER):
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


def _pair(storage, server: str | None, image: str | None = None, role: str = pairing.DEFAULT_ROLE) -> int:
    server = (server or "").strip().rstrip("/") or pairing.server_url(storage)
    if not server:
        print(_("ccc can't tell where the app reaches the API. Put it on the tailnet (tailscale serve --bg 8737) "
                "or give the address: ccc api pair --server https://<computer>.<tailnet>.ts.net"))
        return 1
    code, expires = pairing.new_code(storage, role=role)
    if image is not None:
        path = Path(image).expanduser() if image else Path.home() / "Pictures" / "ccc-pair-qr.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        pairing.save_png(pairing.payload(server, code), path)
        print(_("QR saved as a picture: {path}").format(path=path))
    else:
        # Black on white whatever the terminal's colours: a scanner needs dark modules on a light ground.
        for line in pairing.qr_lines(pairing.payload(server, code)):
            print(f"\033[30;47m{line}\033[0m")
    print(_("Scan it in the app (Connect → Scan QR). Good until {time}, once.").format(time=expires.strftime("%H:%M")))
    print(_("Address: {server}").format(server=server))
    print(_("The phone will be: {role}.").format(role=role))
    return 0
