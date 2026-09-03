# CC-continue

Prompt-queue TUI for Claude Code. Queue prompts per project; CC-continue
runs them headless (`claude -p --resume`) one at a time per project queue,
running multiple projects concurrently, and automatically retries when a
usage-limit block resets. History and basic analytics are kept in
`~/.local/share/cc-continue/history.db`.

## Install

    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"

## Usage

Launch the TUI:

    .venv/bin/cc-continue

Keys: `a` add prompt, `Enter` open queue detail, `v` analytics,
`r` retry a blocked queue, `q` quit.

Queue a prompt without opening the TUI:

    .venv/bin/cc-continue add /path/to/project "do the thing"

## Important

CC-continue only advances queues while it is running — keep it open in a
long-lived tmux/screen session (or a systemd user service) if you want it
to keep working overnight.

All headless runs use `--dangerously-skip-permissions`. Only queue
prompts for projects/prompts you'd trust to run unattended.

## Tests

    .venv/bin/pytest
