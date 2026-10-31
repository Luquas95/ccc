"""What the API's devices did, and the alarms (#160). If a token is ever
misused you need two things: to see afterwards who did what, and to hear of
it while it happens. So the API keeps a log (`ccc api log`, the Devices
window, GET /audit for an admin) and tells the notification channels
(Telegram / Discord, as ccc does for approvals) about what is out of the
ordinary: a new device paired, a wrong pairing code, requests with a wrong
token, a device trying more than its role allows.

Logged: everything that changes something (not GET), every refusal (401 /
403) and every pairing — never the query, the body or typed keys (they can
hold secrets); only the path and, for a new conversation, its folder."""
from __future__ import annotations

import threading
import time
from http import HTTPStatus

from ccc.i18n import _

ALARM_GAP_SECONDS = 300.0  # one alarm of a kind per this long: a scan must not flood the phone
_last_alarm: dict[str, float] = {}
_lock = threading.Lock()


def _spawn(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


def worth_logging(method: str, status: int) -> bool:
    return method != "GET" or status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN)


def record(storage, device, ip: str, method: str, path: str, status: int, detail: str = "") -> None:
    """Never raises: a full disk must not stop the API."""
    try:
        if worth_logging(method, status):
            storage.add_audit(device.id if device else None, device.name if device else "", ip, method, path, int(status), detail[:300])
    except Exception:  # noqa: BLE001
        pass


def alarm(storage, kind: str, text: str, now: float | None = None) -> bool:
    """Tell the notification channels, at most once per ALARM_GAP_SECONDS for the `kind`; True when sent.
    Sent in a thread of its own: a slow Telegram must not hold up a request."""
    from ccc.notify import Notifier

    moment = time.monotonic() if now is None else now
    with _lock:
        if moment - _last_alarm.get(kind, -1e9) < ALARM_GAP_SECONDS:
            return False
        _last_alarm[kind] = moment
    notifier = Notifier(storage)
    if not notifier.configured():
        return False
    _spawn(notifier.send_now, text)
    return True


def alarm_for(storage, status: int, method: str, path: str, ip: str, device) -> None:
    """The alarm, if any, for a request that ended with `status`."""
    if status == HTTPStatus.UNAUTHORIZED and path.endswith("/pair"):
        alarm(storage, "pair-failed", _("ccc API: a wrong pairing code from {ip}.").format(ip=ip))
    elif status == HTTPStatus.UNAUTHORIZED:
        alarm(storage, "bad-token", _("ccc API: a request with a wrong token from {ip}.").format(ip=ip))
    elif status == HTTPStatus.FORBIDDEN and device is not None:
        alarm(storage, f"forbidden-{device.id}", _("ccc API: {name} ({role}) tried {method} {path}, which its role does not allow.").format(
            name=device.name, role=device.role, method=method, path=path))
    elif status == HTTPStatus.CREATED and path.endswith("/pair") and device is not None:
        alarm(storage, f"paired-{device.id}", _("ccc API: a new device was paired: {name} ({role}) from {ip}.").format(
            name=device.name, role=device.role, ip=ip))
