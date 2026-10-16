"""Settings window (Ctrl+P on any screen): look of the app, Telegram and Discord
notifications, how queues continue, launch presets and the database backup —
everything `ccc config` can change, without leaving the TUI."""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Select, Static

from ccc.backup import backup_now, default_backup_dir
from ccc.notify import (
    DISCORD_WEBHOOK_KEY,
    TELEGRAM_CHAT_KEY,
    TELEGRAM_TOKEN_KEY,
    is_discord_webhook,
    send_discord,
    send_telegram,
)
from ccc.analytics_archive import FOLDER_KEY as ARCHIVE_FOLDER_KEY, archive
from ccc.export_paths import (
    FOLDER_KEY as EXPORT_FOLDER_KEY, SEND_CHOICES, SEND_KEY as EXPORT_SEND_KEY, default_export_folder, home_short,
)
from ccc.orchestrator import DEFAULT_CONTINUE_TEXT, RESERVE_KEY, usage_reserve
from ccc.presets import delete_preset, list_presets
from ccc.prompt_presets import MAX_PRESETS, load_prompt_presets, save_prompt_presets
from ccc.tui.layout import MODAL_CSS
from ccc.tui.prompt_presets import PromptPresetModal, mode_label

THEME_KEY = "tui_theme"
RESERVE_CHOICES = [50, 60, 70, 75, 80, 85, 90, 95]
TEST_MESSAGE = "✅ ccc: Telegram notifications work."
DISCORD_TEST_MESSAGE = "✅ ccc: Discord notifications work."
DISCORD_PLACEHOLDER = "https://discord.com/api/webhooks/…"
# Preset prompt table: fixed columns, the prompt gets the rest of the row
# and ends in "…" when it doesn't fit — the full text is in Edit.
PRESET_COLUMNS = (("Key", 5), ("Mode", 8), ("Name", 16))
MIN_PROMPT_WIDTH = 10


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
    SettingsModal #settings-prompt-presets {
        height: auto;
        overflow-x: hidden;
        max-height: 11;
        margin-bottom: 1;
    }
    SettingsModal #settings-prompt-presets > .datatable--cursor {
        background: blue;
        color: white;
        text-style: bold;
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
        discord_set = bool(s.get_setting(DISCORD_WEBHOOK_KEY))
        discord = _section(
            "Discord notifications",
            Static(id="discord-state", classes="settings-hint"),
            _row("Webhook URL", Input(
                password=True,
                placeholder="saved — paste a new one to replace it" if discord_set else DISCORD_PLACEHOLDER,
                id="settings-discord-webhook",
            )),
            Static(
                "In Discord: channel settings → Integrations → Webhooks →\n"
                "New Webhook → Copy Webhook URL. Same messages as Telegram;\n"
                "use either or both. Keep the URL private — anyone who has it\n"
                "can post to the channel.",
                classes="settings-hint",
            ),
            Horizontal(
                Button("Send test message", id="settings-discord-test"),
                Button("Turn off", id="settings-discord-off", classes="settings-danger"),
                Static("", id="discord-test-result", classes="settings-status"),
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
        self._prompt_presets = load_prompt_presets(s)
        prompt_box = _section(
            "Preset prompts",
            Static("Alt+1 … Alt+9 in a conversation: ⏎ send sends it right away, ✎ insert only puts it "
                   "into the message box at the cursor. Shown in the bar under the message box.",
                   classes="settings-hint"),
            DataTable(id="settings-prompt-presets", cursor_type="row"),
            Horizontal(
                Button("Add", id="settings-prompt-add"),
                Button("Edit", id="settings-prompt-edit"),
                Button("Delete", id="settings-prompt-delete", classes="settings-danger"),
                Button("Up", id="settings-prompt-up"),
                Button("Down", id="settings-prompt-down"),
                classes="settings-actions",
            ),
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
        exports = _section(
            "Exports",
            _row("Export folder", Input(s.get_setting(EXPORT_FOLDER_KEY) or "",
                                        placeholder=f"empty = {home_short(default_export_folder())}",
                                        id="settings-export-folder")),
            Static("Exported conversations (e) go to conversations/, screenshots (Ctrl+T) to screenshots/\n"
                   "inside it. Empty = ccc in your documents folder (~/ccc-exports where there is none).",
                   classes="settings-hint"),
            _row("After export", Select(
                [(label, value or "folder") for value, label in SEND_CHOICES],
                value=s.get_setting(EXPORT_SEND_KEY) or "folder", allow_blank=False, id="settings-export-send",
            )),
            Static("Sending puts the file on your phone when ccc runs elsewhere (server, tmux over SSH).\n"
                   "Uses the Telegram / Discord set up above.",
                   classes="settings-hint"),
        )
        archive_box = _section(
            "Monthly analytics archive",
            _row("Folder", Input(s.get_setting(ARCHIVE_FOLDER_KEY) or "", placeholder="empty = off, e.g. ~/Documents/ccc_analytics",
                                 id="settings-archive-folder")),
            Static(
                "The current month is here in Analytics (v). When a month ends, ccc archives it into this\n"
                "folder as Markdown notes for Obsidian (no plugins): ccc_analytics.md with all months, one\n"
                "note per month with a calendar and charts, one per day. Empty = no archive.",
                classes="settings-hint",
            ),
            Horizontal(
                Button("Archive finished months now", id="settings-archive-now"),
                Static("", id="archive-result", classes="settings-status"),
                classes="settings-actions",
            ),
        )
        data = _section(
            "Data",
            Static(id="data-info", classes="settings-status"),
            Static("Backed up automatically every day; the newest 14 copies are kept.", classes="settings-hint"),
            Horizontal(Button("Back up now", id="settings-backup"), classes="settings-actions"),
        )
        box = Container(
            VerticalScroll(appearance, telegram, discord, queues, prompt_box, preset_box, exports, archive_box, data, id="settings-scroll"),
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
        self._refresh_prompt_presets()
        self._refresh_telegram_state()
        self._refresh_discord_state()
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
            "settings-discord-test": self._send_discord_test,
            "settings-discord-off": self._discord_off,
            "settings-preset-delete": self._delete_preset,
            "settings-backup": self._backup,
            "settings-archive-now": self._archive_now,
            "settings-prompt-add": self._add_prompt_preset,
            "settings-prompt-edit": self._edit_prompt_preset,
            "settings-prompt-delete": self._delete_prompt_preset,
            "settings-prompt-up": lambda: self._move_prompt_preset(-1),
            "settings-prompt-down": lambda: self._move_prompt_preset(1),
        }.get(event.button.id or "")
        if handler:
            handler()

    # --- preset prompts (kept in the form until Save) ---------------------

    def _refresh_prompt_presets(self, cursor: int | None = None) -> None:
        table = self.query_one("#settings-prompt-presets", DataTable)
        row = table.cursor_row if cursor is None else cursor
        table.clear(columns=True)
        prompt_width = self._prompt_column_width(table)
        for label, width in PRESET_COLUMNS:
            table.add_column(label, width=width)
        table.add_column("Prompt", width=prompt_width)
        name_width = dict(PRESET_COLUMNS)["Name"]
        for number, preset in enumerate(self._prompt_presets, start=1):
            text = preset.text.strip()
            first_line = text.splitlines()[0] if text else ""
            if "\n" in text:
                first_line += " …"
            table.add_row(f"Alt+{number}", mode_label(preset), _fit(preset.name, name_width),
                          _fit(first_line, prompt_width))
        if not self._prompt_presets:
            table.add_row("", "", Text("no preset prompts yet — Add one", style="dim"), "")
        elif row is not None:
            table.move_cursor(row=max(0, min(row, len(self._prompt_presets) - 1)))
        self.query_one("#settings-prompt-add", Button).disabled = len(self._prompt_presets) >= MAX_PRESETS
        for button in ("edit", "delete", "up", "down"):
            self.query_one(f"#settings-prompt-{button}", Button).disabled = not self._prompt_presets

    @staticmethod
    def _prompt_column_width(table: DataTable) -> int:
        """What's left of the table's width after the fixed columns (each
        column also takes cell_padding on both sides)."""
        fixed = sum(width for _, width in PRESET_COLUMNS)
        padding = 2 * table.cell_padding * (len(PRESET_COLUMNS) + 1)
        return max(MIN_PROMPT_WIDTH, table.scrollable_content_region.width - fixed - padding)

    def on_resize(self) -> None:
        # The prompt column follows the window width.
        self.call_after_refresh(self._refresh_prompt_presets)

    def _selected_prompt_index(self) -> int | None:
        row = self.query_one("#settings-prompt-presets", DataTable).cursor_row
        return row if self._prompt_presets and 0 <= row < len(self._prompt_presets) else None

    def _add_prompt_preset(self) -> None:
        if len(self._prompt_presets) >= MAX_PRESETS:
            return

        def added(preset) -> None:
            if preset is not None:
                self._prompt_presets.append(preset)
                self._refresh_prompt_presets(cursor=len(self._prompt_presets) - 1)

        self.app.push_screen(PromptPresetModal(), added)

    def _edit_prompt_preset(self) -> None:
        index = self._selected_prompt_index()
        if index is None:
            return

        def edited(preset) -> None:
            if preset is not None:
                self._prompt_presets[index] = preset
                self._refresh_prompt_presets(cursor=index)

        self.app.push_screen(PromptPresetModal(self._prompt_presets[index], f"Preset prompt Alt+{index + 1}"), edited)

    def _delete_prompt_preset(self) -> None:
        index = self._selected_prompt_index()
        if index is not None:
            del self._prompt_presets[index]
            self._refresh_prompt_presets(cursor=index)

    def _move_prompt_preset(self, step: int) -> None:
        index = self._selected_prompt_index()
        if index is None or not 0 <= index + step < len(self._prompt_presets):
            return
        p = self._prompt_presets
        p[index], p[index + step] = p[index + step], p[index]
        self._refresh_prompt_presets(cursor=index + step)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "settings-prompt-presets":
            event.stop()
            self._edit_prompt_preset()

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

    # --- Discord -------------------------------------------------------------

    def _refresh_discord_state(self) -> None:
        on = is_discord_webhook(self.storage.get_setting(DISCORD_WEBHOOK_KEY) or "")
        text = Text("● on", style="green") if on else Text("○ off — paste a channel webhook URL", style="yellow")
        self.query_one("#discord-state", Static).update(text)

    def _discord_value(self) -> str:
        return self.query_one("#settings-discord-webhook", Input).value.strip() or (
            self.storage.get_setting(DISCORD_WEBHOOK_KEY) or "")

    def _send_discord_test(self) -> None:
        url = self._discord_value()
        result = self.query_one("#discord-test-result", Static)
        if not is_discord_webhook(url):
            result.update(Text("Paste a Discord webhook URL (https://discord.com/api/webhooks/…) first.", style="yellow"))
            return
        result.update(Text("Sending…", style="dim"))
        self._send_discord_test_worker(url)

    @work(thread=True, exclusive=True, group="discord-test")
    def _send_discord_test_worker(self, url: str) -> None:
        try:
            send_discord(url, DISCORD_TEST_MESSAGE)
            text = Text("✓ Sent — check the Discord channel.", style="green")
        except Exception as exc:  # never show the exception text: it may contain the URL
            text = Text(f"✖ Sending failed ({type(exc).__name__}) — check the webhook URL.", style="red")
        self.app.call_from_thread(self.query_one("#discord-test-result", Static).update, text)

    def _discord_off(self) -> None:
        self.storage.set_setting(DISCORD_WEBHOOK_KEY, "")
        field = self.query_one("#settings-discord-webhook", Input)
        field.value = ""
        field.placeholder = DISCORD_PLACEHOLDER
        self._refresh_discord_state()
        self.query_one("#discord-test-result", Static).update(Text("Discord notifications turned off.", style="dim"))

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

    def _export_folder_value(self) -> str:
        raw = self.query_one("#settings-export-folder", Input).value.strip()
        return str(Path(raw).expanduser()) if raw else ""

    def _archive_folder_value(self) -> str:
        raw = self.query_one("#settings-archive-folder", Input).value.strip()
        return str(Path(raw).expanduser()) if raw else ""

    def _archive_now(self) -> None:
        result = self.query_one("#archive-result", Static)
        if not self._archive_folder_value():
            result.update(Text("Fill in a folder first.", style="yellow"))
            return
        folder = Path(self._archive_folder_value())
        try:
            added = archive(self.storage, folder)
        except OSError as exc:
            result.update(Text(f"✖ Archiving failed: {exc.strerror or type(exc).__name__}", style="red"))
            return
        months = ", ".join(f"{y:04d}-{m:02d}" for y, m in added) or "nothing new to archive"
        result.update(Text(f"✓ {months} — {folder}", style="green"))

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
        webhook = self.query_one("#settings-discord-webhook", Input).value.strip()
        if webhook and not is_discord_webhook(webhook):
            self.notify("That isn't a Discord webhook URL (https://discord.com/api/webhooks/…).",
                        title="Not saved", severity="error")
            return
        s.set_setting(THEME_KEY, self.app.theme)
        token = self.query_one("#settings-telegram-token", Input).value.strip()
        if token:
            s.set_setting(TELEGRAM_TOKEN_KEY, token)
        s.set_setting(TELEGRAM_CHAT_KEY, self.query_one("#settings-telegram-chat", Input).value.strip())
        if webhook:
            s.set_setting(DISCORD_WEBHOOK_KEY, webhook)
        continue_text = self.query_one("#settings-continue-text", Input).value.strip()
        s.set_setting("continue_text", continue_text or DEFAULT_CONTINUE_TEXT)
        reserve = self.query_one("#settings-reserve", Select).value
        s.set_setting(RESERVE_KEY, "" if reserve == "off" else str(reserve))
        save_prompt_presets(s, self._prompt_presets)
        s.set_setting(EXPORT_FOLDER_KEY, self._export_folder_value())
        send = self.query_one("#settings-export-send", Select).value
        s.set_setting(EXPORT_SEND_KEY, "" if send == "folder" else str(send))
        s.set_setting(ARCHIVE_FOLDER_KEY, self._archive_folder_value())
        self.notify("Settings saved.")
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.app.theme = self._original_theme
        self.dismiss(False)


def _fit(text: str, width: int) -> Text:
    """One line, cut to width with "…" at the end."""
    cell = Text(text, no_wrap=True, overflow="ellipsis")
    cell.truncate(width, overflow="ellipsis")
    return cell
