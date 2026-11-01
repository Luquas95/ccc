#!/usr/bin/env bash
# Builds the application tree the .deb installs into /usr/lib/ccc: a virtualenv with ccc and
# its libraries (all pure Python), the TUI supervisor script and the icons.
#
# Usage (from the repo root; needs python3 >= 3.12 with venv):  packaging/build.sh [VERSION]
# VERSION is stamped into the build (the release workflow passes the tag); without it the
# tree is a "0.0.0-dev" build. Result: dist/ccc/ (the venv is relocatable: nothing in it
# is started through its own scripts — /usr/bin/ccc runs `venv/bin/python -m ccc.cli`).
set -euo pipefail
umask 022
cd "$(dirname "$0")/.."

VERSION=${1:-}
app=dist/ccc
rm -rf dist/ccc build/src && mkdir -p "$app" build

# Build from a copy so the stamped version never touches the working tree.
cp -a src build/src && cp pyproject.toml build/ && cp README.md build/ 2>/dev/null || true
[ -z "$VERSION" ] || sed -i "s/^__version__ = .*/__version__ = \"$VERSION\"/" build/src/ccc/__init__.py

python3 -m venv "$app/venv"
"$app/venv/bin/pip" install --quiet --no-cache-dir ./build
rm -rf build
# Only `python -m ccc.…` is used: drop the pip-made scripts (their shebangs name this build dir) and pip itself.
"$app/venv/bin/pip" uninstall --quiet --yes pip 2>/dev/null || true
find "$app/venv/bin" -type f ! -name 'python*' -delete
# Compile now: /usr is read-only for the user, so Python couldn't cache bytecode later.
"$app/venv/bin/python" -m compileall -q "$app/venv/lib" >/dev/null

cp bin/ccc-tui-supervise.sh "$app/ccc-tui-supervise.sh"

# Quick check that the built tree starts and has its data.
"$app/venv/bin/python" -m ccc.cli --version >/dev/null 2>&1 || "$app/venv/bin/python" -c "import ccc, ccc.cli, ccc.daemon, ccc.help"
[ -z "$VERSION" ] || [ "$("$app/venv/bin/python" -c 'import ccc; print(ccc.__version__)')" = "$VERSION" ] \
    || { echo "built version is not $VERSION" >&2; exit 1; }
echo "✓ Built: $app ($(du -sh "$app" | cut -d' ' -f1))"
