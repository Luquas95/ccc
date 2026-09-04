# CC-continue

Prompt-queue tool for Claude Code. Queue prompts per project; a daemon
runs them headless (`claude -p --resume`) one at a time per project,
running multiple projects concurrently, and automatically retries when a
usage-limit block resets — no need to be at the keyboard, no need to keep
any terminal open. A separate TUI lets you look at and add to the queues
whenever you want, without affecting whether they keep running.

History and analytics are kept in `~/.local/share/cc-continue/history.db`
(SQLite).

## Architecture: daemon vs. TUI

- **`cc-continue-daemon`** is the only thing that ever executes prompts.
  It's a headless asyncio process — no TUI, no TTY needed — so it can run
  as a real `systemd --user` service that survives SSH logout, crashes
  (auto-restart), and reboots.
- **`cc-continue`** (the TUI) is a pure viewer/editor: it reads and writes
  the same SQLite database, but never runs a prompt itself. Open it in a
  tmux window when you want to look at something or queue a prompt
  interactively; close it any time — the daemon keeps working regardless.
- Both talk to the same SQLite file, safely: `queue_items` are claimed
  with an atomic `UPDATE ... RETURNING`, so even if you ran two daemons
  by mistake, a prompt is never executed twice.

Headless runs authenticate the same way as your interactive sessions
(OAuth login, not a separate API key) and draw from the **same shared**
5-hour/weekly Pro usage pool as every other Claude Code session on this
machine — there is no separate billing path. The `cost_usd` figures in
the analytics screen are Anthropic's list-price-equivalent for
observability, not an extra charge.

## Install

    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"

## Running the daemon (systemd, recommended)

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/cc-continue.service ~/.config/systemd/user/
systemctl --user daemon-reload
loginctl enable-linger "$USER"   # let it keep running after SSH logout
systemctl --user enable --now cc-continue
```

Check on it:

    systemctl --user status cc-continue
    journalctl --user -u cc-continue -f

Stop/disable it:

    systemctl --user disable --now cc-continue

## Queueing prompts

Without opening anything:

    .venv/bin/cc-continue add /path/to/project "do the thing"

Or interactively, via the TUI — `bin/cc-continue-tmux.sh` opens (or
re-attaches to) a dedicated tmux session running it, handy over SSH:

    ./bin/cc-continue-tmux.sh

TUI keys: `a` add prompt, `s` live sessions, `Enter` open queue detail /
attach to a session, `v` analytics, `r` retry a blocked queue (daemon
picks it back up within ~5s), `q` quit (just closes the viewer — queued
work is unaffected).

### Two delivery modes

- **Headless** (default for `add`/`a`) — the daemon runs
  `claude -p --resume` as a separate subprocess. Safe, gives real
  structured results (tokens, cost, success/failure), but the response
  only ever shows up in cc-continue's own history — never in a terminal.
- **Live terminal** (`s` → pick a session → send) — for continuing a
  session you're actively watching in a tmux pane. The daemon waits until
  `claude agents --json` reports that session idle and not blocked on a
  usage limit, then types the prompt directly into its tmux pane via
  `tmux send-keys`, so it visibly continues that conversation. **This is
  the riskier mode**: there's no reliable way to detect "a human is
  mid-typing something else in that pane right now" — only "Claude itself
  is idle" — so a delivery can in principle interleave with something you
  were about to type. No structured result comes back either (only
  "delivered" or "failed"); the actual response appears in that terminal,
  not in cc-continue.

## Reliability notes

- A queue only blocks (`blocked_error`) on a genuine hard error (bad
  prompt, tool failure, session gone) — never silently loops burning your
  usage limit. Clear it with `r` in the TUI once you've looked at it.
- A real usage-limit hit is detected via `api_error_status == 429` in
  Claude Code's own JSON output (not message-text guessing), and the
  reset time is parsed from the message when present; otherwise it falls
  back to an escalating 15→30→60 min retry.
- New projects queued while the daemon is already running are picked up
  automatically (checked every ~5s), no restart needed.

## Tests

    .venv/bin/pytest
