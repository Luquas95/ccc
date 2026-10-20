# Git: auto-commit & diffs

In a git repository, ccc commits the result of every successful
**headless** task, so each task is one commit you can look at or undo:

- message `ccc: <first line of the task>` with a
  `ccc-conversation: <name>` trailer;
- the queue detail (`Enter` on the [Dashboard](dashboard.md)) shows the
  commit of each run; `Enter` on a run shows its changed files and the
  coloured diff.

## Commenting on a diff

Review Claude's work like a pull request: in a run's diff move to a line
(`↑` `↓`, `PgUp` `PgDn`, a click), press `c` and write what should change
— `Enter` keeps the comment, an empty one removes it. Commented lines get
a `●` and the comments are listed under the diff. `s` sends them all to
the conversation as **one prompt** in its queue: each comment with its
file and line number and the quoted line, and a request to address each
one. Closing the diff with unsent comments asks first.

## Undoing a run

In the queue detail, pick a run with a commit and press `u`: ccc
reverts it with a **new commit** (`git revert`) — nothing is rewritten,
and the revert can be undone in turn. The run then shows `↺` by its
commit. ccc asks whether to **tell Claude** with a short note in the
conversation's queue; otherwise its next task may still assume the
changes are there.

It works when:

- the conversation does nothing at the moment (no task running or
  queued) — a task editing the files would mix its edits into the
  revert;
- the folder has no uncommitted changes, and the commit is in the
  branch's history;
- the conversation was started with **Skip all permission checks** (as
  for the commits themselves, see below).

A revert that conflicts with later changes is abandoned: nothing
changes and ccc says so. From the shell: `ccc runs CONVERSATION` lists
the runs with their ids, `ccc revert RUN [--tell]` undoes one.

## Several conversations in one folder

Two conversations editing the same files at once get in each other's
way, and a commit after one task could take in the other's half-written
changes. So in one git work tree:

- **headless tasks take turns**: a task waits while another
  conversation in the same folder runs one (Conversations says which);
- ccc **doesn't commit** while another conversation works in the folder
  (also an interactive one busy with what you typed) — the run history
  says so;
- Conversations shows a ⚠ line with the others that share the folder.

To let them really work **side by side**, give a conversation its **own
git worktree** when [starting it](new-conversation.md): a separate
checkout of the repository on its own branch (`worktree-<name>`, in
`.claude/worktrees/<name>` — where `claude --worktree <name>` keeps
its own, left out of the main checkout's `git status`). ccc commits its
tasks there; merge the branch when you're happy with it. Remove a
worktree you no longer need with `git worktree remove .claude/worktrees/<name>`.

A fresh checkout has only the tracked files, so `.env`, local
certificates or config the project needs to run would be missing. List
them in a **`.worktreeinclude`** file at the repository's top (gitignore
syntax — the same file Claude Code, Conductor and Codex read), e.g.:

```
.env
config/local.json
```

ccc copies into each new worktree the files that match a pattern **and**
are ignored by git — never a tracked file, never through a symbolic link,
never over an existing file, at most 500 files of up to 20 MB each.

## When ccc doesn't commit

The run history says why:

- the folder already had **uncommitted changes** before the task — that's
  your work, ccc never sweeps it into its commit;
- nothing changed, or the repository is on a detached HEAD;
- the conversation wasn't started with **Skip all permission checks**.
  ccc runs git itself, outside Claude's permission mode, so in an
  *Auto-accept edits* / *Plan only* conversation Claude could otherwise
  slip a git hook in that ccc would run;
- the repository's config uses filters, includes or signing (or changed
  during the task) — for safety ccc then runs no git there.

Conversations with Claude Code beside ccc aren't committed by ccc — Claude
commits there itself when you ask it to.
