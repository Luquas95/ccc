# Command line

Everything ccc does can be reached from the TUI; a few things also work
from the shell — e.g. in scripts or over SSH. The commands live in the
checkout's virtualenv (`~/ccc/.venv/bin/`); add it to your `PATH` or call
them with the full path.

| Command | |
|---|---|
| `ccc` | open ccc |
| `ccc add <folder> "<prompt>"` | queue a prompt for that folder's conversation (it runs headless) |
| `ccc backup` | back up the database now |
| `ccc archive-analytics` | write finished months into the [monthly analytics archive](analytics.md) now |
| `ccc config analytics-folder [PATH\|off]` | show / set / turn off the monthly archive folder |
| `ccc config continue-text ["…"]` | show / set the continue message sent after a usage limit |
| `ccc config usage-reserve [N\|off]` | show / set the [usage reserve](limits.md) |
| `ccc config telegram-token [TOKEN]` | show (masked) / set the Telegram bot token |
| `ccc config telegram-chat [ID]` | show / set the Telegram chat id |
| `ccc config telegram-test` | send a test message to Telegram |
| `ccc config discord-webhook [URL\|off]` | show (masked) / set / remove the Discord webhook |
| `ccc config discord-test` | send a test message to Discord |
| `ccc-daemon` | the daemon itself (normally run by `ccc.service`) |
