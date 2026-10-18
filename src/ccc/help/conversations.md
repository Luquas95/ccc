# Conversations

Conversations (`c`) is where you work with Claude. On the left is the list
of your conversations, on the right the selected one. Move in the list
with `↑` `↓` — the right side follows at once.

![Conversations](../../../docs/screenshots/conversations.png)

## The list

Each conversation shows a marker in front of its name and `·N` behind it
when N tasks wait in its [queue](tasks.md):

| Marker | Meaning |
|---|---|
| `●` | Claude is working |
| `‖` | waiting for a usage-limit reset, or paused |
| `✖` | stopped on an error — needs you |
| `?` | Claude is waiting for you to [approve a tool call](approvals.md) |
| `◆` | a new reply you haven't looked at yet |

With no conversation at all, the right side says **NO CONVERSATION** —
press `n` to start one.

## Claude Code beside ccc

A conversation started with `n` runs the **real Claude Code** — the same
as typing `claude` in a terminal, with every feature: slash commands,
tool approvals, `Shift+Tab`, `Esc Esc`, history, images. ccc shows it to
the right of its menu:

| Key | |
|---|---|
| `Enter` on a conversation | open its Claude Code and put the keyboard there |
| `Alt+0` | switch the keyboard between ccc and Claude (or click where you want to type) |
| `Ctrl+]` | close Claude's pane — Claude keeps running, `Enter` opens it again |
| select with the mouse | copies to your clipboard (also over SSH and in Termux) |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | copy the selection / paste the last copy |

Under Claude a bar shows your [preset prompts](settings.md) — click one
to use it. `Alt+0` and `Ctrl+]` are also in ccc's bar at the bottom.

Good to know:

- Claude keeps running when you switch to another conversation or screen,
  close ccc (`Ctrl+Q`) or close the pane. The daemon keeps it alive in the
  background and starts it again with its history if it dies.
- Tasks from the [queue](tasks.md) are pasted into Claude whenever it's
  idle, as if you typed them.
- On a narrow window (under 100 columns, e.g. a phone) Claude takes the
  whole window; `Alt+0` gets you back to ccc.
- Every such conversation keeps a Claude Code process in memory —
  [archive](archive.md) (`x`) the ones you're done with.

## Headless conversations

Prompts queued with `a` (Live sessions, queue detail) or `ccc add` run
**headless**: the daemon runs `claude -p` for each task, without a
terminal. For these ccc shows the transcript itself:

- Claude's replies are rendered as Markdown; a tool call is a collapsed
  `▸ ⚙ Tool: …` line — `Enter` or a click shows its input and result.
- The **message box** under the transcript adds a message to the end of
  the queue: `Enter` sends, `Ctrl+J` starts a new line. `Alt+1` … `Alt+9`
  send or insert a [preset prompt](settings.md).
- The line above the box says what's going on: *Ready*, *Next task at
  23:00*, *Waiting for usage limit reset until 14:30*,
  *✖ Blocked: … — press r to retry*, …
- A headless run can't stop and ask you to approve a tool, so its
  permission mode is chosen up front — see
  [Approving tool calls](approvals.md).

## The header

At the top: the conversation's name, project folder and Claude Code
options, whether auto-continue is on, and for a
[remote-control](remote-control.md) conversation the link for your phone.

## Other keys

| Key | |
|---|---|
| `t` | the [task queue](tasks.md) of this conversation |
| `r` | stopped on an error: run the failed task again; paused at a limit: carry on — see [Usage limits](limits.md) |
| `p` | [approve a tool call](approvals.md) Claude is waiting on |
| `x` | [archive](archive.md) the conversation |
| `/` | search all conversations (archived too); `Enter` on a hit opens it |
| `e` | export the conversation as Markdown (to `conversations/` in the export folder, see [Settings](settings.md)) |
| `n` | [start a new conversation](new-conversation.md) |
