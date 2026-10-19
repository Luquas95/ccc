# Git: auto-commit & diffs

In a git repository, ccc commits the result of every successful
**headless** task, so each task is one commit you can look at or undo:

- message `ccc: <first line of the task>` with a
  `ccc-conversation: <name>` trailer;
- the queue detail (`Enter` on the [Dashboard](dashboard.md)) shows the
  commit of each run; `Enter` on a run shows its changed files and the
  coloured diff.

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
