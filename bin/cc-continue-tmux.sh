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
# SSH-persistence session) or not: from inside tmux it deliberately nests
# (TMUX unset), since switch-client can't cross to a different tmux server.
# Detach the inner one with the prefix pressed twice (Ctrl+B Ctrl+B D).
set -euo pipefail

# The TUI runs on its own tmux server/socket, separate from your default
# one (see deploy/systemd/cc-continue-tui.service for why).
TMUX_SOCKET="cc-continue"
SESSION="cc-continue"
PROJECT_DIR="/home/lukas/DEV/CC-continue"
RUN_CMD="while true; do $PROJECT_DIR/.venv/bin/cc-continue; sleep 1; done"

if tmux -L "$TMUX_SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    # A client can't switch-client across tmux servers, so from inside
    # another tmux session we attach with $TMUX unset (nested on purpose).
    TMUX= exec tmux -L "$TMUX_SOCKET" attach-session -t "$SESSION"
else
    TMUX= exec tmux -L "$TMUX_SOCKET" new-session -s "$SESSION" -c "$PROJECT_DIR" "$RUN_CMD"
fi
