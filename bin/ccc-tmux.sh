#!/usr/bin/env bash
# Kept for old habits / scripts: same as plain `ccc`, which attaches to the
# one ccc instance (the "ccc" tmux session run by the ccc-tui service) or
# starts it when it isn't running — see src/ccc/instance.py.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
exec "$PROJECT_DIR/.venv/bin/ccc" "$@"
