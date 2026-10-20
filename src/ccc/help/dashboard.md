# Dashboard

The Dashboard (`d`) is the overview: every conversation with what it's
doing right now. It's only for looking — you work with a conversation in
[Conversations](conversations.md).

![Dashboard](../../../docs/screenshots/dashboard.png)

## Overview

The top line counts all conversations: how many Claude is working on
(**running**), how many tasks wait in their queues (**pending**), how
many stopped on an error (**blocked**, red), and how many tokens they used
today.

## The table

One row per conversation (archived ones are in the [Archive](archive.md)):

| Column | |
|---|---|
| Project | the conversation's name, with its marker (see below) |
| Status | what it's doing — see the table below |
| Pending | tasks waiting in its [queue](tasks.md) |
| Today's tokens | tokens it used today |
| Path | the project folder Claude works in |

**Markers** in front of the name — the same in the Conversations list:

| Marker | Meaning |
|---|---|
| `●` | Claude is working |
| `‖` | waiting for a usage-limit reset, or paused |
| `✖` | stopped on an error — needs you |
| `?` | Claude is waiting for you to [approve a tool call](approvals.md) |
| `◆` | a new reply you haven't looked at yet |

In the Conversations list `·3` after the name means three tasks queued.

**Status:**

| Status | |
|---|---|
| `idle` | nothing to do; the next task starts as soon as you add one |
| `running` | Claude is working on a task |
| `waiting_retry` | waiting for a usage limit to reset; then it carries on by itself |
| `paused_limit` | stopped at a usage limit with auto-continue off — waits for you |
| `blocked_error` | stopped on an error — waits for you |

What to do with the last two: [Usage limits & blocked queues](limits.md).

## Queue detail

`Enter` on a row opens the conversation's detail:

- its settings (folder, Claude Code options, auto-continue) and, for a
  [remote-control](remote-control.md) conversation, the link to open it
  on your phone;
- the **run history**: every task with its result, tokens and — in a git
  repository — its commit. `Enter` on a run shows the commit's diff (see
  [Git](git.md));
- `+` adds a task to this conversation, `r` gets it going again when it's
  blocked or paused at a limit. `Esc` goes back.

![Queue detail](../../../docs/screenshots/queue_detail.png)

## An empty Dashboard

Before your first conversation the Dashboard shows **Getting started**
instead — three steps to begin. Press `n`.
