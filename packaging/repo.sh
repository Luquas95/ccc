#!/usr/bin/env bash
# From the release .deb (dist/release, see packaging/package.sh) makes the signed flat APT
# repository for GitHub Pages in dist/site/:
#   apt/       Packages, Release, InRelease, Release.gpg and the .deb
#   ccc.asc    the public release key
#
# Usage: GNUPGHOME=<keyring with the release key> packaging/repo.sh VERSION
# Needs apt-ftparchive (apt-utils) and gpg. The repository holds only the newest version.
set -euo pipefail
umask 022
cd "$(dirname "$0")/.."

VERSION=${1:?usage: packaging/repo.sh VERSION}
fpr=$(gpg --show-keys --with-colons packaging/signing-key.asc | awk -F: '/^fpr/ {print $10; exit}')
site=dist/site
sign=(gpg --batch --yes --local-user "$fpr")
rm -rf "$site" && mkdir -p "$site/apt"
cp packaging/signing-key.asc "$site/ccc.asc"

cp dist/release/ccc_all.deb "$site/apt/ccc_${VERSION}_all.deb"
(
    cd "$site/apt"
    apt-ftparchive packages . > Packages
    gzip -9kn Packages
    apt-ftparchive \
        -o APT::FTPArchive::Release::Origin=ccc \
        -o APT::FTPArchive::Release::Label=ccc \
        -o APT::FTPArchive::Release::Architectures=all \
        release . > Release
    "${sign[@]}" --clearsign --output InRelease Release
    "${sign[@]}" --armor --detach-sign --output Release.gpg Release
)

cat > "$site/index.html" <<HTML
<!doctype html><meta charset="utf-8"><title>ccc – APT repository</title>
<p>APT repository of <a href="https://github.com/Luquas95/ccc">ccc</a> (version ${VERSION}).
Install the package from the
<a href="https://github.com/Luquas95/ccc/releases/latest">latest release</a> –
the repository sets itself up and later versions arrive with the system update.</p>
HTML
touch "$site/.nojekyll"
find "$site" -type f | sort
