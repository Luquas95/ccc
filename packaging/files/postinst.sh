#!/bin/sh
# Shown after installing/upgrading the package. Nothing is started for the user: the services are
# per-user (systemd --user), so every user enables them once.
set -e
cat <<'MSG'

ccc is installed. As your user (not root), once:
    systemctl --user enable --now ccc ccc-tui
    loginctl enable-linger "$USER"      # keep them running after you log out
then open it with: ccc
(After an upgrade: systemctl --user restart ccc ccc-tui)

MSG
