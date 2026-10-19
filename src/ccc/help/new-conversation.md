# Starting a conversation

Press `n` anywhere (or the green **New conversation** button in
Conversations). The window has two halves.

![New conversation](../../../docs/screenshots/new_conversation.png)

## Directory

The project folder Claude will work in: pick one of the recent folders,
browse the folder tree, or type a path.

## Options

The same switches as on the `claude` command line. Groups marked *one*
allow only one choice.

| Group | Options |
|---|---|
| Session (*one*) | **New session** · **Continue last in directory** · **Resume selected…** (pick one of the folder's past Claude Code sessions) · **From pull request…** |
| | **As a copy (fork)** — with Continue / Resume / From PR: a new conversation that starts from that one, the original stays as it was |
| Permissions (*one*) | **Skip all permission checks** — Claude does everything without asking · **Auto-accept edits** — file edits yes, other tools ask · **Plan only** — Claude only plans |
| Model (*one*) | Opus · Sonnet · Haiku · Fable |
| Effort (*one*) | high · xhigh · max |
| Other | Fallback to Sonnet when overloaded · Claude in Chrome · Safe mode |

Below them:

- **Auto-continue after usage limit** (on by default) — when Claude hits
  your usage limit, the conversation waits for the reset and carries on by
  itself. Off: it stops and waits for you. See
  [Usage limits](limits.md).
- **Remote control (phone / claude.ai)** — you can also continue the
  conversation from the Claude mobile app. See
  [Remote control](remote-control.md).

Nothing ticked means Claude Code's own defaults.

## Presets

The window remembers your last choice. If you use a few combinations
often, **Save as preset** stores the current one under a name; **Choose a
preset…** fills the window with it. Delete presets in
[Settings](settings.md).

## After Start

You're in [Conversations](conversations.md) with Claude Code open beside
ccc. Resuming a session that already has a conversation in ccc just
switches to that conversation — unless you tick *As a copy (fork)*.
