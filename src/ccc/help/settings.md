# Settings & notifications

`Ctrl+P` opens Settings — everything you can change, in one window.
Change what you need, then `Ctrl+S` (*Save*). `Esc` (*Cancel*) throws the
changes away. Buttons like *Send test message*, *Turn off* or *Back up
now* act right away.

![Settings](../../../docs/screenshots/settings.png)

## Sections

| Section | |
|---|---|
| Appearance | language — *Auto* follows the system (`LANG`), saving another one restarts ccc's window; colour theme — changes as you pick, kept after Save |
| Telegram notifications | see below |
| Discord notifications | see below |
| Queues | the *continue* text sent after a usage limit, and the usage reserve — see [Usage limits](limits.md); the [reviewer's](review.md) model |
| Preset prompts | your prompts on `Alt+1` … `Alt+9` — see below |
| New-conversation presets | delete presets saved in the [New conversation](new-conversation.md) window |
| Keyboard shortcuts | change any key, export / import them — see below |
| Exports | the folder for exported conversations (`e`) and screenshots (`Alt+S`); optionally send each export to Telegram / Discord |
| Monthly analytics archive | see [Analytics](analytics.md) |
| Data | where the database and its daily backups are, *Back up now* |

The same values can be set from the shell, see
[Command line](command-line.md).

## Preset prompts

Prompts you type again and again — "go on", "run the tests and fix what
fails", "review this file: " — saved once, used in any conversation with
`Alt+1` … `Alt+9`.

- **Set up:** *Preset prompts* → *Add* / *Edit*: a **name** (shown in the
  bar), the **prompt** and **Send right away (with Enter)**. *Up* /
  *Down* set the order — the first is `Alt+1`. Up to 9.
- **Use:** press the key or click the preset in the bar.
  - `⏎` presets are **sent** at once.
  - `✎` presets are **put into the message box** (or Claude's input) for
    you to finish, e.g. add a file name.

![Preset prompt editor](../../../docs/screenshots/prompt_preset.png)

## Keyboard shortcuts

Every key in ccc can be changed: *Keyboard shortcuts* → *Edit
shortcuts…* opens a window listing every action with its key (changed
ones in yellow).

- **Change:** pick an action, then *Press the key* and press its new key
  (any key — Esc, Ctrl+P too), or type its name (`Ctrl+O`, `Alt+S`, `F5`,
  `+`) and *Set*. *Default* puts one back, *All defaults* all of them.
- **Checked first:** a key that collides is refused, and the window says
  why — it's never saved. A collision is:
  - another action on the same key where both work at once (e.g. two
    views, or a view and a key that works everywhere),
  - a key the terminal can't tell apart (Ctrl+I is Tab, Ctrl+M is Enter,
    Ctrl+H is Backspace), Ctrl+C, Ctrl+B (tmux's prefix) or
    Ctrl+Shift+C / V (copy / paste),
  - a key the lists and text fields need (arrows, Enter, Tab, Space,
    editing keys like Ctrl+A / E / K / U / W),
  - for keys that also work from the Claude Code pane (switch, close
    Claude, presets, Settings, screenshot, close ccc): one of Claude
    Code's keys (Ctrl+T, Ctrl+O, Ctrl+R, Alt+P, …), or a key without
    Ctrl / Alt (F-keys are fine) — it couldn't be typed into Claude
    Code any more.
- **Save** (`Ctrl+S`) and the new keys work right away — the menu, the
  buttons and `?` show them. This window saves on its own, independently
  of Settings' Save.
- **Export / Import:** type a folder (the export folder is prefilled) —
  *Export* writes `ccc-keys.json` there, *Import* reads it (or the file
  you name) and is checked the same way: one collision and nothing is
  imported. Copy the file to another machine to take your keys along.

The same from the shell: `ccc keys` (see [Command line](command-line.md)).
The other pages of this guide name the default keys.

## Telegram notifications

ccc messages you when a conversation **finished its queue**, **stopped on
an error**, **needs you** (paused at a limit, a tool approval waiting) or
**hit a usage limit** and later **continues**.

1. In Telegram, create a bot with [@BotFather](https://t.me/BotFather)
   (`/newbot`) and copy its token.
2. Send your bot any message, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy
   the number after `"chat":{"id":`.
3. Fill in both in Settings, press *Send test message*, then *Save*.

## Discord notifications

The same messages can go to a Discord channel — instead of Telegram or
as well.

1. In Discord: the channel's settings → *Integrations* → *Webhooks* →
   *New Webhook* → *Copy Webhook URL*.
2. Paste it in Settings, press *Send test message*, then *Save*.

Keep the URL private: anyone who has it can post to the channel.
Tokens and webhooks are stored in ccc's database, shown masked and never
logged.

## Backups

The daemon backs up ccc's database every day and keeps the last 14
(`~/.local/share/ccc/backups/`). To restore one, see
[Troubleshooting](troubleshooting.md).
