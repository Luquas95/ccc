"""The Devices window: who is signed in to the API (phones), the button
that pairs a new one by QR code (ccc.pairing), and signing one out."""
from __future__ import annotations

from rich.text import Text
from textual import work
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from ccc import keymap, pairing
from ccc.i18n import _
from ccc.storage import Storage
from ccc.tui.layout import MODAL_CSS


class DevicesModal(ModalScreen):
    DEFAULT_CSS = MODAL_CSS.format(cls="DevicesModal") + """
    DevicesModal #devices-table {
        height: auto;
        max-height: 10;
        margin-bottom: 1;
    }
    DevicesModal #devices-qr {
        width: auto;
        height: auto;
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
            Static(id="devices-qr"),
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
        table.add_columns(_("Device"), _("Last seen"), _("Address"))
        self._refresh()

    def _refresh(self, keep: int | None = None) -> None:
        table = self.query_one("#devices-table", DataTable)
        table.clear()
        devices = self.storage.list_devices()
        for device in devices:
            seen = device.last_seen_at.strftime("%Y-%m-%d %H:%M") if device.last_seen_at else _("never")
            table.add_row(device.name, seen, device.last_ip or "—", key=str(device.id))
        if devices and keep is not None:
            table.move_cursor(row=min(keep, len(devices) - 1))
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
        self._info(Text(_("Looking for the API's address…"), style="dim"))
        self._pair_worker()

    @work(thread=True, exclusive=True, group="pair")
    def _pair_worker(self) -> None:
        server = pairing.server_url(self.storage)
        shown = None
        if server:
            code, expires = pairing.new_code(self.storage)
            shown = (pairing.qr_lines(pairing.payload(server, code)), server, expires)
        self.app.call_from_thread(self._paired, shown)

    def _paired(self, shown) -> None:
        qr = self.query_one("#devices-qr", Static)
        if shown is None:
            qr.update("")
            self._info(Text(_("ccc can't tell where the app reaches the API. Put it on the tailnet "
                              "(tailscale serve --bg 8737) or run: ccc api pair --server https://…"), style="yellow"))
            return
        lines, server, expires = shown
        qr.update(Text("\n".join(lines), style="black on white", no_wrap=True))
        self._info(Text(_("Scan it in the app (Connect → Scan QR). Good until {time}, once.").format(
            time=expires.strftime("%H:%M")) + "\n" + _("Address: {server}").format(server=server), style="green"))

    def _revoke(self) -> None:
        table = self.query_one("#devices-table", DataTable)
        if not table.row_count:
            return
        row = table.cursor_row
        device_id = int(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        self.storage.delete_device(device_id)
        self._refresh(keep=row)
        self.query_one("#devices-qr", Static).update("")
        if table.row_count:
            self._info(Text(_("Signed out."), style="green"))

    def action_close(self) -> None:
        self.dismiss(None)
