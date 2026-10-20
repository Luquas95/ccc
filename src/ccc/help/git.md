# Git: auto-commit & diffs

In a git repository, ccc commits the result of every successful
**headless** task, so each task is one commit you can look at or undo:

- message `ccc: <first line of the task>` with a
  `ccc-conversation: <name>` trailer;
- the queue detail (`Enter` on the [Dashboard](dashboard.md)) shows the
  commit of each run; `Enter` on a run shows its changed files and the
  coloured diff.

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
