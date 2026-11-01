#!/usr/bin/env bash
# From the built tree (dist/ccc, see packaging/build.sh) makes the release files in dist/release/:
# ccc_all.deb and SHA256SUMS (packaging/sign.sh signs it).
#
# Usage: packaging/package.sh VERSION     (needs nfpm in PATH)
set -euo pipefail
umask 022
cd "$(dirname "$0")/.."

VERSION=${1:?usage: packaging/package.sh VERSION}
export VERSION
out=dist/release
[ -x dist/ccc/venv/bin/python ] || { echo "dist/ccc is missing — run packaging/build.sh first" >&2; exit 1; }
built=$(dist/ccc/venv/bin/python -c 'import ccc; print(ccc.__version__)')
[ "$built" = "$VERSION" ] || { echo "Built version $built ≠ $VERSION" >&2; exit 1; }
rm -rf "$out" && mkdir -p "$out"

nfpm package --config packaging/nfpm.yaml --packager deb --target "$out/ccc_all.deb"
(cd "$out" && sha256sum ccc_all.deb > SHA256SUMS)
ls -l "$out"
