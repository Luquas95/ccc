# ccc

Prompt-queue tool for Claude Code. Queue prompts per project; a daemon
runs them headless (`claude -p --resume`) one at a time per project,
running multiple projects concurrently, and automatically retries when a
usage-limit block resets — no need to be at the keyboard, no need to keep
any terminal open. A separate TUI lets you look at and add to the queues
whenever you want, without affecting whether they keep running.

History and analytics are kept in `~/.local/share/ccc/history.db`
(SQLite).

## Architecture: daemon vs. TUI

- **`ccc-daemon`** is the only thing that ever executes prompts.
  It's a headless asyncio process — no TUI, no TTY needed — so it can run
  as a real `systemd --user` service that survives SSH logout, crashes
  (auto-restart), and reboots.
- **`ccc`** (the TUI) is a pure viewer/editor: it reads and writes
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
cp deploy/systemd/ccc.service ~/.config/systemd/user/
systemctl --user daemon-reload
loginctl enable-linger "$USER"   # let it keep running after SSH logout
systemctl --user enable --now ccc
```

Check on it:

    systemctl --user status ccc
    journalctl --user -u ccc -f

Stop/disable it:

    systemctl --user disable --now ccc

### Encrypted home (ecryptfs)

If your home directory is ecryptfs-encrypted, linger alone isn't enough:
the user systemd manager starts at boot, before login, while
`~/.config/systemd/user/` is still unreadable — so the units silently
never start. Start them at login instead, e.g. with an XFCE/GNOME
autostart entry (`~/.config/autostart/ccc-units.desktop`) that
runs:

    systemctl --user daemon-reload
    systemctl --user start ccc.service ccc-tui.service

## Running the TUI (systemd + tmux, always attachable)

The TUI can run the same way: a `ccc-tui` systemd unit boots a
persistent tmux session named `ccc` at startup, with `ccc` running
inside it in a restart loop — so it's always alive and ready. Quitting the
TUI (`q`) just makes it reappear a second later in the same pane; the
session is never left dead. Attach any time with `bin/ccc-tmux.sh`
(or plain `tmux -L ccc attach -t ccc`) and detach
(`Ctrl+B D`) or just close the terminal/SSH connection whenever — it
keeps running either way.

The TUI runs on its **own tmux server** (socket `-L ccc`), not
your default one, so it doesn't show up in plain `tmux ls`. That's
deliberate: if the unit started your default tmux server, all your other
tmux sessions would live in this unit's cgroup and systemd-oomd killing
it would take them all down. If the session dies anyway (oomd, crash,
`kill-server`), the unit notices within ~5s and recreates it.

```bash
cp deploy/systemd/ccc-tui.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ccc-tui
```

(Needs `loginctl enable-linger "$USER"` too, same as the daemon above, so
it survives SSH logout — skip if you already ran that for the daemon.)

Attach to it:

    ./bin/ccc-tmux.sh

Stop/disable it (kills the tmux session too):

    systemctl --user disable --now ccc-tui

## Queueing prompts

Without opening anything:

    .venv/bin/ccc add /path/to/project "do the thing"

Every TUI screen shares one layout (modelled on the conversations view):
a left sidebar with the **Views** list (Dashboard / Conversations / Live
sessions / Analytics — the current one highlighted, clickable), the
screen's own list where it has one, and coloured action buttons at the
bottom; content on the right sits in round-bordered panels.

TUI keys, available on every screen: `d` dashboard, `c` conversations,
`s` live sessions, `v` analytics, `n` new conversation, `a` add prompt
(path prefilled from the selected queue). Plus: `Enter` open queue detail / attach to a session,
`r` retry a blocked queue or resume one paused at a usage limit (daemon
picks it back up within ~5s; on the sessions screen `r` refreshes
instead), `t` task queue editor (conversations view), `Esc` back, `q` quit on the
dashboard (just closes the viewer — queued work is unaffected).

### Two delivery modes

- **Headless** (default for `add`/`a`) — the daemon runs
  `claude -p --resume` as a separate subprocess. Safe, gives real
  structured results (tokens, cost, success/failure), but the response
  only ever shows up in ccc's own history — never in a terminal.
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
  not in ccc.

### Starting a new conversation

Press `n` anywhere (or the green **New conversation** button in the
conversations view). The dialog has:

- **Directory** — recent directories, a directory tree from `~/DEV`, or
  type a path.
- **Attributes** to tick (groups marked *one* are exclusive):

  | Group | Options |
  |---|---|
  | Session (*one*) | New session · Continue last in directory · Resume selected… (pick from that directory's past sessions) · From pull request… (`--from-pr`) |
  | | As a copy (fork) — `--fork-session`, with any of the resuming options |
  | Permissions (*one*) | Skip all permission checks · Auto-accept edits · Plan only |
  | Model (*one*) | Opus · Sonnet · Haiku · Fable |
  | Effort (*one*) | high · xhigh · max |
  | Other | Fallback to Sonnet when overloaded · Claude in Chrome · Safe mode |

After **Start** the conversation opens in the conversations view; type in
the box under the transcript and press Enter. Each message is queued and
run by the daemon as `claude -p --resume … <your attributes>`, so
conversations started here also keep going across usage limits and with
the TUI closed. While a message waits it shows as a grey *queued* bubble;
the status line says whether Claude is working, waiting for a limit reset,
or blocked.

Because runs are headless, Claude can't ask you to approve a tool mid-run
and interactive slash commands aren't available — choose the permission
mode up front. Resuming a session that already has a conversation in
ccc just switches to it (unless you fork). A fork / from-PR
conversation adopts the new session id Claude Code returns on its first
run.

### Remote control (phone / claude.ai)

*Remote control* in the New conversation dialog is ticked by default.
Such a conversation doesn't run headless message by message: the daemon
keeps an interactive `claude --remote-control <name>` running for it in a
hidden tmux server (`tmux -L ccc-sessions`, session `q<id>`), so
you can also continue it from the Claude mobile app or claude.ai — the
link appears in the conversation header and the queue detail. (Headless
`claude -p` silently ignores `--remote-control`; it needs a live process.)

- Messages from the TUI and the task queue are pasted into it once Claude
  is idle (multi-line prompts as a single paste). Messages sent from the
  phone show up in the same transcript.
- The daemon starts the process after the conversation is created, after
  a daemon restart, and if it dies (`--resume` keeps the history); it
  accepts the folder-trust dialog only right after starting it, never
  any tool-permission prompt. Archiving (`x`) or deleting stops it.
- Usage limits: if the session gets blocked mid-work, a continue message
  is queued first and sent after the reset (auto-continue) or when you
  press `r`.
- Each such conversation keeps a Claude Code process in memory; archive
  the ones you don't use. Runs aren't counted in the token analytics
  (interactive sessions return no structured result).

### Telegram notifications

The daemon can message you on Telegram when a conversation **finished its
queue** (with the start of the reply), **needs you** (paused at a usage
limit with auto-continue off), **stopped on an error**, or **hit a usage
limit** (waiting until HH:MM) and later **continues**.

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and
   copy its token.
2. Send your bot any message, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy
   `"chat":{"id": …}`.
3. Configure and test:

       ccc config telegram-token <TOKEN>
       ccc config telegram-chat <CHAT_ID>
       ccc config telegram-test

Without both values nothing is sent. The token is stored in the ccc
database, shown masked, and never logged.

### Usage limits and auto-continue

Each conversation has an **auto-continue** switch (on by default; a
checkbox in the New conversation dialog, `o` in the Tasks editor).

- The daemon reads the account's real usage (5-hour, weekly and any
  per-model window — the same figures as the Analytics screen). Before it
  starts a message it checks them: while a window is used up it doesn't
  even start Claude, it waits for that window's reset (+30 s).
- After Claude Code reports a usage limit (429), the wait is the busiest
  window's reset; if usage can't be read it falls back to the time in the
  error message, then to a 15→30→60 min backoff.
- **Auto-continue on:** after the reset the conversation carries on by
  itself. **Off:** it stops in `paused_limit` and waits for you — press `r`
  or just send another message.
- If the limit cut a message off after it had reached the conversation,
  the retry sends a short continue message instead of repeating it:
  `ccc config continue-text` shows it, `ccc config
  continue-text "…"` changes it (default *Pokračuj tam, kde jsi skončil.*).
- Waiting survives daemon restarts (the reset time is stored).

### Auto-commit and diffs

In a git repository, every successful headless task is committed:
`ccc: <first line of the task>` with a `ccc-conversation: <name>`
trailer. It's skipped — and the reason recorded — when the working tree
already had uncommitted changes before the task (that's your work, it is
never swept into a ccc commit), on a detached HEAD, or when nothing
changed. Auto-commit only happens in conversations started with *Skip all
permission checks*: the daemon runs git outside Claude's permission mode,
so in an *Auto-accept edits* / *Plan only* conversation Claude could
otherwise plant a git hook or config that ccc would execute for it. Every
git call also disables hooks, fsmonitor, external diff/textconv and the
pager. The queue detail shows a *Commit* column; Enter on a run opens
the commit's stat and coloured diff.

### Task queue

A conversation works through its queued messages one after another, in
the same session — the next starts as soon as Claude finishes the previous
one. Press `t` in the conversations view to edit that queue:

| Key | |
|---|---|
| `a` | add a task (multi-line editor, `Ctrl+S` save, `Esc` cancel) |
| `e` / `Enter` | edit the selected task |
| `Delete` | remove it (kept in history as skipped) |
| `Ctrl+↑` / `Ctrl+↓` | move it up / down |
| `p` | pause / resume the queue (a running task finishes) |
| `o` | toggle auto-continue |

The message box under the transcript adds to the end of the same queue.

### Conversation list: markers, archive, delete

Each conversation in the list (and on the dashboard) shows what it's doing:
`●` Claude is working · `‖` waiting for a usage-limit reset / paused ·
`✖` blocked on an error · `◆` a new reply you haven't looked at yet —
followed by `·N` queued tasks.

In the conversations view: `x` archives the selected conversation (hidden
from the lists, still processed; `h` shows archived ones, `x` again
restores), `Ctrl+D` deletes it after confirmation — its queued tasks and
run history go, Claude Code's own transcript stays (so it can still be
picked under *Resume selected…*). A conversation Claude is working on
can't be deleted until it finishes or you pause it.

### Reading, searching, exporting

Claude's replies render as Markdown; a tool call is a collapsed `▸ ⚙
Tool: …` line — Enter/click shows its full input and its result. The
message box under the transcript is multi-line: Enter sends, Ctrl+J (or
Shift+Enter where the terminal reports it) starts a new line. In the
conversations view `/` searches every conversation (archived too) and
Enter on a hit opens it; `e` exports the selected conversation as
Markdown to `~/Documents/ccc-exports/`. The sidebar shows whether the
daemon is running. The New conversation dialog remembers your last
choice and can save it as a named preset.

### Conversations view

Press `c` on the dashboard to see a queue's full conversation — not just
the last result. Arrow keys in the left-hand queue list immediately
switch which queue's transcript is shown on the right. This reads Claude
Code's own JSONL session transcript
(`~/.claude/projects/**/<session_id>.jsonl`) directly, so it works
identically for headless and live-terminal queues, and stays live: while
the screen is open, the currently-shown queue's transcript is re-checked
every ~2s for new messages (e.g. from a live-terminal session someone is
actively typing in).

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
