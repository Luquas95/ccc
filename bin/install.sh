#!/usr/bin/env bash
# Installs ccc for the current user:
#   - a virtualenv in this checkout with ccc installed into it,
#   - systemd --user units for the daemon (ccc.service) and the always-on
#     TUI in tmux (ccc-tui.service), generated for this checkout's path,
#   - enables and starts them.
#
# Usage: bin/install.sh [--no-tui] [--no-start] [--no-systemd] [--units-dir DIR]
#   --no-tui      only the daemon unit (run the TUI yourself with .venv/bin/ccc)
#   --no-start    enable the units but don't start them now
#   --no-systemd  only create the venv; don't touch systemd at all
#   --units-dir   write the units somewhere else to inspect them (systemd is
#                 then left alone)
# Safe to re-run (e.g. after `git pull`): it reinstalls and rewrites units.
set -euo pipefail

CCC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
DEFAULT_UNITS_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNITS_DIR="$DEFAULT_UNITS_DIR"
WITH_TUI=1
START=1
SYSTEMD=1

while [ $# -gt 0 ]; do
    case "$1" in
        --no-tui) WITH_TUI=0 ;;
        --no-start) START=0 ;;
        --no-systemd) SYSTEMD=0 ;;
        --units-dir) UNITS_DIR="$2"; shift ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }

# --- requirements ------------------------------------------------------------
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' \
    || { echo "ccc needs Python 3.12 or newer (found $(python3 --version))" >&2; exit 1; }
command -v claude >/dev/null || warn "Claude Code CLI ('claude') not found in PATH — install it and log in before queueing prompts."
if [ "$WITH_TUI" = 1 ] && [ "$SYSTEMD" = 1 ]; then
    command -v tmux >/dev/null || { echo "tmux is needed for the always-on TUI (or use --no-tui)" >&2; exit 1; }
fi

# --- virtualenv ---------------------------------------------------------------
if [ ! -x "$CCC_DIR/.venv/bin/python" ]; then
    say "Creating virtualenv in $CCC_DIR/.venv"
    python3 -m venv "$CCC_DIR/.venv"
fi
say "Installing ccc into the virtualenv"
"$CCC_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$CCC_DIR/.venv/bin/pip" install --quiet -e "$CCC_DIR"

if [ "$SYSTEMD" = 0 ]; then
    say "Done. Start the daemon with $CCC_DIR/.venv/bin/ccc-daemon and the TUI with $CCC_DIR/.venv/bin/ccc"
    exit 0
fi

# --- systemd user units --------------------------------------------------------
mkdir -p "$UNITS_DIR"
units=(ccc.service)
[ "$WITH_TUI" = 1 ] && units+=(ccc-tui.service)
for unit in "${units[@]}"; do
    sed "s#@CCC_DIR@#$CCC_DIR#g" "$CCC_DIR/deploy/systemd/$unit" > "$UNITS_DIR/$unit"
    say "Wrote $UNITS_DIR/$unit"
done

if [ "$UNITS_DIR" != "$DEFAULT_UNITS_DIR" ]; then
    say "Units written to $UNITS_DIR only (systemd not touched)."
    exit 0
elif command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
    systemctl --user daemon-reload
    if [ "$START" = 1 ]; then
        systemctl --user enable --now "${units[@]}"
        say "Started: ${units[*]}"
    else
        systemctl --user enable "${units[@]}"
        say "Enabled (not started): ${units[*]}"
    fi
    if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null || echo no)" != "yes" ]; then
        warn "linger is off — the services stop when you log out. Enable it with: loginctl enable-linger $USER"
    fi
else
    warn "systemd --user isn't available here; units written but not enabled."
fi

say "All set. Open the TUI: $CCC_DIR/bin/ccc-tmux.sh   (or .venv/bin/ccc)"
