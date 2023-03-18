#!/bin/bash -eu

# update-local-repo.sh: Add all available packages to the custom repository,
# initialising it if necessary
echo "-> Archlinux update-local-repo.sh"

CHROOT_DIR="$1"
PKGS_DIR="$2"

if [ "${VERBOSE:-0}" -ge 2 ] || [ "${DEBUG:-0}" -eq 1 ]; then
    set -x
fi

chroot_cmd() {
    sudo systemd-nspawn --directory="$CHROOT_DIR" \
        --keep-unit \
        --register=no \
        --register=no \
        --bind="${PKGS_DIR}":"/tmp/qubes-packages-mirror-repo" \
        --chdir=/tmp/qubes-packages-mirror-repo \
        "$@"
}

mkdir -p "$PKGS_DIR"
if [ ! -f "${PKGS_DIR}/qubes.db" ]; then
    echo "  -> Repo '${PKGS_DIR}' appears empty; initialising..."
    chroot_cmd repo-add qubes.db.tar.gz
fi

set -e

# Generate custom repository metadata based on packages that are available
# Repo Add need packages to be added in the right version number order as it only keeps the last entered package version
chroot_cmd /bin/sh -c 'for pkg in `find . -name "*.pkg.tar.*"`; do repo-add qubes.db.tar.gz "$pkg"; done;'

# Ensure pacman doesn't check for disk free space -- it doesn't work in chroots
chroot_cmd sed "s/^ *CheckSpace/#CheckSpace/g" -i /etc/pacman.conf

# Update archlinux keyring first so that Archlinux can be updated even after a long time
chroot_cmd /bin/sh -c \
    "http_proxy='${REPO_PROXY}' pacman -Sy --noconfirm archlinux-keyring"

# Now update system
chroot_cmd /bin/sh -c \
    "http_proxy='${REPO_PROXY}' pacman -Syu --noconfirm"
