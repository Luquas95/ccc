# Live sessions

Live sessions (`s`) lists **every Claude Code session running on this
machine** — also the ones you started yourself in a terminal, outside
ccc — with its status and folder.

![Live sessions](../../../docs/screenshots/sessions.png)

| Key | |
|---|---|
| `Enter` | send the selected session a prompt |
| `r` | reload the list |
| `+` | add a prompt to any project's queue (runs [headless](conversations.md)) |

## Sending a prompt to a running session

`Enter` on a session queues a prompt for it. ccc waits until that Claude
is idle, then types the prompt into its terminal — you see it continue
there. The reply appears in that terminal, not in ccc.

Be careful with a terminal you're typing in yourself: ccc can tell that
*Claude* is idle, not that *you* are in the middle of typing, so the two
could mix. For work you want to hand over to ccc, a conversation started
with `n` is the better choice.

A session from a terminal appears in ccc's Dashboard and Conversations
once you send it a prompt this way.
