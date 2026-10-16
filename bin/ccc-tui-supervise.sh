#!/usr/bin/env bash
# Runs as ExecStart of the ccc-tui systemd unit: creates the
# detached "ccc" tmux session (on its own tmux socket, see
# TMUX_SOCKET) with the TUI in a restart loop, then blocks for as long as
# that session exists. Exits non-zero as soon as the session is gone, so
# systemd's Restart=always recreates it.
#
# Not meant to be run by hand — `ccc` attaches to it.
set -euo pipefail

# -f /dev/null when the server starts: no user tmux.conf, so no plugins.
# tmux-continuum/resurrect would otherwise restore the user's sessions
# (even re-launching `claude --continue` in them) into this server.
TMUX_SOCKET="ccc"
SESSION="ccc"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_CMD="while true; do $PROJECT_DIR/.venv/bin/ccc tui; sleep 1; done"

if ! tmux -L "$TMUX_SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    tmux -L "$TMUX_SOCKET" -f /dev/null new-session -d -s "$SESSION" -x 200 -y 50 -c "$PROJECT_DIR" "$RUN_CMD"
fi

while tmux -L "$TMUX_SOCKET" has-session -t "$SESSION" 2>/dev/null; do
    sleep 5
done

echo "tmux session $SESSION is gone, exiting so systemd restarts it" >&2
exit 1
