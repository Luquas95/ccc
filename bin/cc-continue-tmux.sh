#!/usr/bin/env bash
# Attaches to the persistent "cc-continue" tmux session running the TUI.
#
# Normally this session already exists — the cc-continue-tui systemd unit
# creates it at boot, running cc-continue in a restart loop, so the app
# is always live and ready to attach to. Quitting the TUI (q) just makes
# it reappear a second later; the session itself is never left dead. This
# script's fallback branch (session missing) recreates it the same way,
# in case the systemd unit isn't installed/running for some reason.
#
# This is purely a convenience viewer/editor — with cc-continue-daemon
# running as its own systemd service, queued prompts execute regardless
# of whether this TUI or its tmux session exists at all.
#
# Safe to run whether you're already inside a tmux session (e.g. your own
# SSH-persistence session) or not — nesting tmux inside tmux would
# otherwise fail with "sessions should be nested with care".
set -euo pipefail

SESSION="cc-continue"
PROJECT_DIR="/home/lukas/DEV/CC-continue"
RUN_CMD="while true; do $PROJECT_DIR/.venv/bin/cc-continue; sleep 1; done"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    if [ -n "${TMUX:-}" ]; then
        exec tmux switch-client -t "$SESSION"
    else
        exec tmux attach-session -t "$SESSION"
    fi
else
    if [ -n "${TMUX:-}" ]; then
        tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR" "$RUN_CMD"
        exec tmux switch-client -t "$SESSION"
    else
        exec tmux new-session -s "$SESSION" -c "$PROJECT_DIR" "$RUN_CMD"
    fi
fi
