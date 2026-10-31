"""The Devices window: who is signed in to the API (phones), the button
that pairs a new one by QR code (ccc.pairing), and signing one out."""
from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual import work
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from ccc import keymap, pairing
from ccc.i18n import _
from ccc.models import REVOKED_BY_COMPUTER
from ccc.storage import Storage
from ccc.tui.layout import MODAL_CSS


class PairModal(ModalScreen):
    """The QR code of a pairing, in a window of its own (it is tall: beside the
    device list it pushed the list and the buttons off a normal terminal, #131).
    Closes by itself once the phone has used the code; dismisses with the new
    device's name, else None."""

    DEFAULT_CSS = MODAL_CSS.format(cls="PairModal") + """
    PairModal #pair-qr {
        width: auto;
        height: auto;
        margin-bottom: 1;
    }
    PairModal .modal-buttons {
        height: 3;
    }
    """

    BINDINGS = [keymap.binding("window.cancel", "close", _("Close"))]

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        self._waiting: str | None = None  # the stored pairing code while the QR is shown
        self._expires: datetime | None = None
        self._known: set[int] = set()

    def compose(self):
        box = Container(
            Static(id="pair-qr"),
            Static(Text(_("Looking for the API's address…"), style="dim"), id="pair-info"),
            Horizontal(Button(_("Close"), id="pair-close", classes="modal-cancel"), classes="modal-buttons"),
        )
        box.border_title = _("Pair a new device")
        yield box

    def on_mount(self) -> None:
        self.set_interval(1.5, self._watch)
        self._make_code()

    def _info(self, text: Text | str) -> None:
        self.query_one("#pair-info", Static).update(text)

    @work(thread=True, exclusive=True, group="pair")
    def _make_code(self) -> None:
        server = pairing.server_url(self.storage)
        shown = None
        if server:
            code, expires = pairing.new_code(self.storage)
            shown = (pairing.qr_lines(pairing.payload(server, code)), server, expires,
                     self.storage.get_setting(pairing.CODE_KEY), {d.id for d in self.storage.list_devices()})
        self.app.call_from_thread(self._shown, shown)

    def _shown(self, shown) -> None:
        if shown is None:
            self._info(Text(_("ccc can't tell where the app reaches the API. Put it on the tailnet "
                              "(tailscale serve --bg 8737) or run: ccc api pair --server https://…"), style="yellow"))
            return
        lines, server, expires, stored, known = shown
        self._waiting, self._expires, self._known = stored, expires, known
        self.query_one("#pair-qr", Static).update(Text("\n".join(lines), style="black on white", no_wrap=True))
        self._info(Text(_("Scan it in the app (Connect → Scan QR). Good until {time}, once.").format(
            time=expires.strftime("%H:%M")) + "\n" + _("Address: {server}").format(server=server), style="green"))

    def _watch(self) -> None:
        """Once the phone has used the code (it is gone from the settings), close; when it runs out unused, say so."""
        if self._waiting is None:
            return
        if self.storage.get_setting(pairing.CODE_KEY) == self._waiting:
            if self._expires and datetime.now() > self._expires:
                self._waiting = None
                self.query_one("#pair-qr", Static).update("")
                self._info(Text(_("The code has run out. Pair again for a new one."), style="yellow"))
            return
        self._waiting = None
        new = [d for d in self.storage.list_devices() if d.id not in self._known]
        self.dismiss(new[-1].name if new else None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_close()

    def action_close(self) -> None:
        self.dismiss(None)


class DevicesModal(ModalScreen):
    DEFAULT_CSS = MODAL_CSS.format(cls="DevicesModal") + """
    DevicesModal #devices-table {
        height: auto;
        max-height: 14;
        margin-bottom: 1;
    }
    DevicesModal #devices-info {
        margin-bottom: 1;
    }
    DevicesModal .modal-buttons {
        height: 3;
    }
    DevicesModal .modal-buttons Button {
        margin-right: 1;
    }
    """

    BINDINGS = [keymap.binding("window.cancel", "close", _("Close"))]

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage

    def compose(self):
        box = Container(
            DataTable(id="devices-table", cursor_type="row", zebra_stripes=True),
            Static(id="devices-info"),
            Horizontal(
                Button(_("Pair a new device"), id="devices-pair", classes="modal-submit"),
                Button(_("Sign out"), id="devices-revoke"),
                Button(_("Close"), id="devices-close", classes="modal-cancel"),
                classes="modal-buttons",
            ),
        )
        box.border_title = _("Devices")
        yield box

    def on_mount(self) -> None:
        table = self.query_one("#devices-table", DataTable)
        table.add_columns(_("Device"), _("Paired"), _("Last seen"), _("Address"))
        self._refresh()
        self.set_interval(3, self._refresh)  # a phone signed out elsewhere disappears by itself

    @staticmethod
    def _when(moment: datetime | None) -> str:
        return moment.strftime("%Y-%m-%d %H:%M") if moment else _("never")

    def _refresh(self, select: int | None = None) -> None:
        """Reload the list, keeping the selected device (or selecting `select`)."""
        table = self.query_one("#devices-table", DataTable)
        if select is None and table.row_count:
            select = int(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        row = table.cursor_row
        devices = self.storage.list_devices()
        table.clear()
        for device in devices:
            table.add_row(device.name, self._when(device.created_at), self._when(device.last_seen_at),
                          device.last_ip or "—", key=str(device.id))
        ids = [d.id for d in devices]
        if ids:
            table.move_cursor(row=ids.index(select) if select in ids else min(row, len(ids) - 1))
        self.query_one("#devices-revoke", Button).disabled = not devices
        if not devices:
            self._info(Text(_("No device is signed in yet — pair one."), style="dim"))

    def _info(self, text: Text | str) -> None:
        self.query_one("#devices-info", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        {"devices-pair": self._pair, "devices-revoke": self._revoke, "devices-close": self.action_close}.get(
            event.button.id or "", lambda: None)()

    def _pair(self) -> None:
        self.app.push_screen(PairModal(self.storage), self._paired)

    def _paired(self, name: str | None) -> None:
        self._refresh()
        if name:
            table = self.query_one("#devices-table", DataTable)
            for index, device in enumerate(self.storage.list_devices()):
                if device.name == name:
                    table.move_cursor(row=index)
            self._info(Text(_("Paired: {name}").format(name=name), style="green"))

    def _revoke(self) -> None:
        table = self.query_one("#devices-table", DataTable)
        if not table.row_count:
            return
        device_id = int(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        self.storage.revoke_device(device_id, REVOKED_BY_COMPUTER)
        self._refresh()
        if table.row_count:
            self._info(Text(_("Signed out."), style="green"))

    def action_close(self) -> None:
        self.dismiss(None)
