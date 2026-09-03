#!/usr/bin/env bash
# Opens (or attaches to) a tmux session running the CC-continue TUI.
#
# This is purely a convenience viewer/editor — with cc-continue-daemon
# running as a systemd service, queued prompts execute regardless of
# whether this tmux session exists. Use this only when you want to look
# at the dashboard or add a prompt interactively over SSH.
set -euo pipefail

SESSION="cc-continue"
PROJECT_DIR="/home/lukas/DEV/CC-continue"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    exec tmux attach-session -t "$SESSION"
else
    exec tmux new-session -s "$SESSION" -c "$PROJECT_DIR" "$PROJECT_DIR/.venv/bin/cc-continue"
fi
