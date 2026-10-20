# Reviews

The Claude that just spent forty steps writing a change is a poor judge
of it: it remembers why every line seemed right. A **review** is a
separate Claude Code run with a **clean context**. It reads what the
conversation changed and ends with one verdict:

| Verdict | |
|---|---|
| **PASS** | it checked the changes and found nothing wrong |
| **FAIL** | something is wrong; it says where (file:line) and what |
| **PARTIAL** | it couldn't verify part of it, and says why |

Press `v` in [Conversations](conversations.md) or in the queue detail to
open the **Review** window of the selected conversation.

## Asking for a review

- Optionally write **what to check first** ("the error paths, not the
  happy path"). Empty = it checks the changes for correctness.
- **Until it passes**: every verdict other than PASS goes back to the
  conversation as a task (the findings), and once Claude has fixed them,
  the next round reviews again. It stops at PASS, at the round limit (5 by
  default, at most 12), or when you press **Stop**.
- **Start review** (`Ctrl+S`). The review waits until the conversation is
  idle (nothing running or queued) and the [usage limits](limits.md)
  allow it, then the daemon runs it. The window shows it as it goes; the
  verdict also comes to Telegram / Discord when they're set up.

## What gets reviewed

What the conversation changed **since the last review**:

1. the [commits ccc made](git.md) for its tasks;
2. without those, the uncommitted changes in its git repository;
3. without git, the files of its tasks since then (the reviewer gets
   the tasks and what Claude said it did).

Nothing new: no model is called, the review says *nothing new*.

The reviewer **can't change or run anything**: it can only read and
search files, everything else is refused. ccc gives it the diff itself.
It loads only your own Claude Code settings, none from the project it
reviews (no permissions, hooks or MCP servers from that repository). Its
run isn't saved as a Claude Code session; its tokens count in
[Analytics](analytics.md) like a task's.

## After the verdict

Pick a review in the list to read its report. For FAIL / PARTIAL, **Send
findings to the conversation** adds them as a task (until it passes does
that by itself).

The reviewer's model is in [Settings](settings.md) → Queues → *Reviewer
model*: by default the conversation's own model. A strong model pays off
here: a missed bug costs more than the review.

From the shell: `ccc review` (see [Command line](command-line.md)). With
`--wait` the exit code is the verdict, e.g. for CI.
