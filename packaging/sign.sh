#!/usr/bin/env bash
# Signs the release's SHA256SUMS (dist/release/SHA256SUMS.asc) with ccc's release key
# (packaging/signing-key.asc). Icenux (github.com/Luquas95/icenux) takes the package from the
# release only when this signature is valid and the checksum fits.
#
# Usage: GNUPGHOME=<keyring with the release key> packaging/sign.sh
set -euo pipefail
cd "$(dirname "$0")/.."
fpr=$(gpg --show-keys --with-colons packaging/signing-key.asc | awk -F: '/^fpr/ {print $10; exit}')
gpg --batch --yes --local-user "$fpr" --armor --detach-sign \
    --output dist/release/SHA256SUMS.asc dist/release/SHA256SUMS
gpg --batch --verify dist/release/SHA256SUMS.asc dist/release/SHA256SUMS
