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
| Queues | the *continue* text sent after a usage limit, and the usage reserve — see [Usage limits](limits.md) |
| Preset prompts | your prompts on `Alt+1` … `Alt+9` — see below |
| New-conversation presets | delete presets saved in the [New conversation](new-conversation.md) window |
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
