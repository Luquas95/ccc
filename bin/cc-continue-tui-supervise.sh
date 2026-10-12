#!/usr/bin/env bash
# Runs as ExecStart of the cc-continue-tui systemd unit: creates the
# detached "cc-continue" tmux session (on its own tmux socket, see
# TMUX_SOCKET) with the TUI in a restart loop, then blocks for as long as
# that session exists. Exits non-zero as soon as the session is gone, so
# systemd's Restart=always recreates it.
#
# Not meant to be run by hand — use bin/cc-continue-tmux.sh to attach.
set -euo pipefail

TMUX_SOCKET="cc-continue"
SESSION="cc-continue"
PROJECT_DIR="/home/lukas/DEV/CC-continue"
RUN_CMD="while true; do $PROJECT_DIR/.venv/bin/cc-continue; sleep 1; done"

if ! tmux -L "$TMUX_SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    tmux -L "$TMUX_SOCKET" new-session -d -s "$SESSION" -x 200 -y 50 -c "$PROJECT_DIR" "$RUN_CMD"
fi

while tmux -L "$TMUX_SOCKET" has-session -t "$SESSION" 2>/dev/null; do
    sleep 5
done

echo "tmux session $SESSION is gone, exiting so systemd restarts it" >&2
exit 1
