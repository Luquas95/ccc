"""Settings window (Ctrl+P on any screen): look of the app, Telegram
notifications, how queues continue, launch presets and the database backup —
everything `ccc config` can change, without leaving the TUI."""
from __future__ import annotations

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from ccc.backup import backup_now, default_backup_dir
from ccc.notify import TELEGRAM_CHAT_KEY, TELEGRAM_TOKEN_KEY, send_telegram
from ccc.orchestrator import DEFAULT_CONTINUE_TEXT, RESERVE_KEY, usage_reserve
from ccc.presets import delete_preset, list_presets
from ccc.tui.layout import MODAL_CSS

THEME_KEY = "tui_theme"
RESERVE_CHOICES = [50, 60, 70, 75, 80, 85, 90, 95]
TEST_MESSAGE = "✅ ccc: Telegram notifications work."


def saved_theme(storage, available) -> str | None:
    theme = storage.get_setting(THEME_KEY)
    return theme if theme in available else None


def _section(title: str, *children) -> Vertical:
    box = Vertical(*children, classes="settings-section")
    box.border_title = title
    return box


def _row(label: str, widget) -> Horizontal:
    return Horizontal(Static(label, classes="settings-label"), widget, classes="settings-row")


class SettingsModal(ModalScreen):
    """Changes are kept in the form until Save; the theme previews live and
    is put back on Cancel. Test message and backup act immediately."""

    DEFAULT_CSS = MODAL_CSS.format(cls="SettingsModal") + """
    SettingsModal > Container {
        width: 90%;
        max-width: 110;
        height: 90%;
    }
    SettingsModal #settings-scroll {
        height: 1fr;
    }
    SettingsModal .settings-section {
        border: round cyan;
        border-title-color: green;
        border-title-style: bold;
        padding: 0 1;
        margin-bottom: 1;
        height: auto;
    }
    SettingsModal .settings-row {
        height: auto;
    }
    SettingsModal .settings-label {
        width: 18;
        padding-top: 1;
        text-style: bold;
    }
    SettingsModal .settings-row Input, SettingsModal .settings-row Select {
        width: 1fr;
        margin-bottom: 0;
    }
    SettingsModal .settings-hint {
        color: $text-muted;
        padding-left: 18;
        margin-bottom: 1;
    }
    SettingsModal .settings-actions {
        height: 3;
        margin-bottom: 1;
    }
    SettingsModal .settings-actions Button {
        border: none;
        height: 3;
        margin-right: 1;
        background: blue;
        color: white;
        text-style: bold;
    }
    SettingsModal .settings-actions Button.settings-danger {
        background: red;
    }
    SettingsModal .settings-status {
        padding-top: 1;
    }
    SettingsModal .modal-hint {
        color: $text-muted;
        width: 1fr;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, storage):
        super().__init__()
        self.storage = storage

    # --- layout ------------------------------------------------------------

    def compose(self):
        s = self.storage
        themes = sorted(self.app.available_themes)
        self._original_theme = self.app.theme
        token_set = bool(s.get_setting(TELEGRAM_TOKEN_KEY))
        reserve = usage_reserve(s)
        reserve_values = sorted(set(RESERVE_CHOICES) | ({reserve} if reserve else set()))

        appearance = _section(
            "Appearance",
            _row("Theme", Select([(t, t) for t in themes], value=self.app.theme, allow_blank=False, id="settings-theme")),
            Static("Applied right away so you can see it; kept after Save.", classes="settings-hint"),
        )
        telegram = _section(
            "Telegram notifications",
            Static(id="telegram-state", classes="settings-hint"),
            _row("Bot token", Input(
                password=True,
                placeholder="saved — type a new one to replace it" if token_set else "123456:ABC… from @BotFather",
                id="settings-telegram-token",
            )),
            _row("Chat ID", Input(s.get_setting(TELEGRAM_CHAT_KEY) or "", placeholder="e.g. 123456789",
                                  id="settings-telegram-chat")),
            Static(
                "Create a bot with @BotFather, send it any message, then open\n"
                "api.telegram.org/bot<TOKEN>/getUpdates — the chat id is under \"chat\": {\"id\": …}.\n"
                "You get a message when a queue finishes, needs you, fails or hits a usage limit.",
                classes="settings-hint",
            ),
            Horizontal(
                Button("Send test message", id="settings-telegram-test"),
                Button("Turn off", id="settings-telegram-off", classes="settings-danger"),
                Static("", id="telegram-test-result", classes="settings-status"),
                classes="settings-actions",
            ),
        )
        queues = _section(
            "Queues",
            _row("Continue text", Input(s.get_setting("continue_text", DEFAULT_CONTINUE_TEXT) or DEFAULT_CONTINUE_TEXT,
                                        id="settings-continue-text")),
            Static("Sent by auto-continue when a conversation stopped at a usage limit.", classes="settings-hint"),
            _row("Usage reserve", Select(
                [("Off", "off")] + [(f"{p} %", str(p)) for p in reserve_values],
                value=str(reserve) if reserve else "off", allow_blank=False, id="settings-reserve",
            )),
            Static("Queued tasks wait while a usage window (5 h / weekly) is at or above this.", classes="settings-hint"),
        )
        presets = list_presets(s)
        preset_box = _section(
            "New-conversation presets",
            _row("Preset", Select([(n, n) for n in sorted(presets)], prompt="no presets saved" if not presets else "choose…",
                                  id="settings-preset", disabled=not presets)),
            Static("Presets are saved in the New conversation window (n → Save as preset).", classes="settings-hint"),
            Horizontal(Button("Delete preset", id="settings-preset-delete", classes="settings-danger",
                              disabled=not presets), classes="settings-actions"),
        )
        data = _section(
            "Data",
            Static(id="data-info", classes="settings-status"),
            Static("Backed up automatically every day; the newest 14 copies are kept.", classes="settings-hint"),
            Horizontal(Button("Back up now", id="settings-backup"), classes="settings-actions"),
        )
        box = Container(
            VerticalScroll(appearance, telegram, queues, preset_box, data, id="settings-scroll"),
            Horizontal(
                Static("Ctrl+S save  ·  Esc cancel", classes="modal-hint"),
                Button("Cancel", id="settings-cancel", classes="modal-cancel"),
                Button("Save", id="settings-save", classes="modal-submit"),
                classes="modal-buttons",
            ),
        )
        box.border_title = "Settings"
        yield box

    def on_mount(self) -> None:
        self._refresh_telegram_state()
        self._refresh_data_info()
        self.query_one("#settings-theme", Select).focus()

    def _refresh_telegram_state(self) -> None:
        on = bool(self.storage.get_setting(TELEGRAM_TOKEN_KEY)) and bool(self.storage.get_setting(TELEGRAM_CHAT_KEY))
        text = Text("● on", style="green") if on else Text("○ off — fill in the bot token and chat id", style="yellow")
        self.query_one("#telegram-state", Static).update(text)

    def _refresh_data_info(self) -> None:
        backups = sorted(default_backup_dir(self.storage.db_path).glob("history-*.db"))
        last = backups[-1].name.removeprefix("history-").removesuffix(".db") if backups else "never"
        self.query_one("#data-info", Static).update(Text.assemble(
            ("Database  ", "bold"), self.storage.db_path, "\n",
            ("Backups   ", "bold"), str(default_backup_dir(self.storage.db_path)), f"  (last: {last})",
        ))

    # --- events ------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "settings-theme" and isinstance(event.value, str):
            self.app.theme = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        handler = {
            "settings-save": self.action_save,
            "settings-cancel": self.action_cancel,
            "settings-telegram-test": self._send_test,
            "settings-telegram-off": self._telegram_off,
            "settings-preset-delete": self._delete_preset,
            "settings-backup": self._backup,
        }.get(event.button.id or "")
        if handler:
            handler()

    def _telegram_values(self) -> tuple[str, str]:
        token = self.query_one("#settings-telegram-token", Input).value.strip() or (
            self.storage.get_setting(TELEGRAM_TOKEN_KEY) or "")
        chat = self.query_one("#settings-telegram-chat", Input).value.strip()
        return token, chat

    def _send_test(self) -> None:
        token, chat = self._telegram_values()
        result = self.query_one("#telegram-test-result", Static)
        if not token or not chat:
            result.update(Text("Fill in the bot token and chat id first.", style="yellow"))
            return
        result.update(Text("Sending…", style="dim"))
        self._send_test_worker(token, chat)

    @work(thread=True, exclusive=True)
    def _send_test_worker(self, token: str, chat: str) -> None:
        try:
            send_telegram(token, chat, TEST_MESSAGE)
            text = Text("✓ Sent — check Telegram.", style="green")
        except Exception as exc:  # never show the exception text: it may contain the token
            text = Text(f"✖ Sending failed ({type(exc).__name__}) — check the token and chat id.", style="red")
        self.app.call_from_thread(self.query_one("#telegram-test-result", Static).update, text)

    def _telegram_off(self) -> None:
        self.storage.set_setting(TELEGRAM_TOKEN_KEY, "")
        self.storage.set_setting(TELEGRAM_CHAT_KEY, "")
        self.query_one("#settings-telegram-token", Input).value = ""
        self.query_one("#settings-telegram-token", Input).placeholder = "123456:ABC… from @BotFather"
        self.query_one("#settings-telegram-chat", Input).value = ""
        self._refresh_telegram_state()
        self.query_one("#telegram-test-result", Static).update(Text("Telegram notifications turned off.", style="dim"))

    def _delete_preset(self) -> None:
        select = self.query_one("#settings-preset", Select)
        if not isinstance(select.value, str):
            self.notify("Choose a preset first.", severity="warning")
            return
        name = select.value
        delete_preset(self.storage, name)
        remaining = sorted(list_presets(self.storage))
        select.set_options([(n, n) for n in remaining])
        if not remaining:
            select.disabled = True
            self.query_one("#settings-preset-delete", Button).disabled = True
        self.notify(f"Preset “{name}” deleted.")

    def _backup(self) -> None:
        try:
            path = backup_now(self.storage.db_path, default_backup_dir(self.storage.db_path))
        except Exception as exc:
            self.notify(f"Backup failed: {type(exc).__name__}", severity="error")
            return
        self._refresh_data_info()
        self.notify(str(path), title="Backed up")

    # --- save / cancel -----------------------------------------------------

    def action_save(self) -> None:
        s = self.storage
        s.set_setting(THEME_KEY, self.app.theme)
        token = self.query_one("#settings-telegram-token", Input).value.strip()
        if token:
            s.set_setting(TELEGRAM_TOKEN_KEY, token)
        s.set_setting(TELEGRAM_CHAT_KEY, self.query_one("#settings-telegram-chat", Input).value.strip())
        continue_text = self.query_one("#settings-continue-text", Input).value.strip()
        s.set_setting("continue_text", continue_text or DEFAULT_CONTINUE_TEXT)
        reserve = self.query_one("#settings-reserve", Select).value
        s.set_setting(RESERVE_KEY, "" if reserve == "off" else str(reserve))
        self.notify("Settings saved.")
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.app.theme = self._original_theme
        self.dismiss(False)
