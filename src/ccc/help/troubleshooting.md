# Troubleshooting & how it works

## The sidebar says "daemon not running"

Nothing gets done without the daemon. Check and start it:

```bash
systemctl --user status ccc        # is it running?
systemctl --user restart ccc
journalctl --user -u ccc -f        # its log
```

To keep it running after you log out or close SSH, enable lingering once:
`loginctl enable-linger "$USER"`.

**Encrypted home (ecryptfs):** the services can't start at boot, before
you log in, because their files are still encrypted. Start them at login
instead, e.g. with an autostart entry of your desktop that runs
`systemctl --user daemon-reload && systemctl --user start ccc.service ccc-tui.service`.

## `ccc` doesn't open / shows something odd

The always-on ccc runs in its own tmux server (`tmux -L ccc`), so it
doesn't show up in plain `tmux ls`. `ccc` attaches to it; if the
`ccc-tui` service isn't running, `ccc` starts it. If ccc itself quits, it
is back a second later. `systemctl --user restart ccc-tui` restarts it.

## A conversation stopped

`✖` = stopped on an error, `‖` = waiting for a usage limit or paused.
See [Usage limits & blocked queues](limits.md).

## Restoring a backup

1. `systemctl --user stop ccc ccc-tui`
2. Copy a backup from `~/.local/share/ccc/backups/` over
   `~/.local/share/ccc/history.db`.
3. `systemctl --user start ccc ccc-tui`

## How ccc works

- **`ccc-daemon`** is the only thing that ever runs Claude. It's a
  background service that survives SSH logout, crashes (it's restarted)
  and reboots.
- **The TUI** only reads and writes ccc's database; it never runs a
  prompt. Close it any time.
- Both share one SQLite database (`~/.local/share/ccc/history.db`); a task
  is claimed atomically, so it never runs twice.
- Conversations with Claude Code beside ccc run as interactive `claude`
  processes in a hidden tmux server (`tmux -L ccc-sessions`), kept alive
  by the daemon.
- ccc uses your normal Claude Code login — no API key — and the **same**
  5-hour / weekly usage as any other Claude Code session on the machine.
  Costs shown are Anthropic's list-price equivalent, not an extra charge.
- A usage limit is recognised from Claude Code's own error status (429),
  not by guessing from text. When the reset time is unknown, ccc retries
  after 15, then 30, then 60 minutes.
