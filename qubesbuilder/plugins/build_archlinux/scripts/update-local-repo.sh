#!/bin/sh

# update-local-repo.sh: Add all available packages to the custom repository,
# initialising it if necessary
echo "-> Archlinux update-local-repo.sh"

CHROOT_DIR="$1"
BUILDER_REPO_DIR="$2"

PKGS_DIR="${BUILDER_REPO_DIR}/pkgs"

if [ "${VERBOSE:-0}" -ge 2 ] || [ "${DEBUG:-0}" -eq 1 ]; then
    set -x
fi

chroot_cmd() {
    systemd-nspawn --directory="$CHROOT_DIR" \
        --keep-unit \
        --register=no \
        --as-pid2 \
        --bind="${BUILDER_REPO_DIR}":"/builder/repository" \
        --chdir=/builder/repository \
        "$@"
}

mkdir -p "$PKGS_DIR"
if [ ! -f "${PKGS_DIR}/qubes.db" ]; then
    echo "  -> Repo '${PKGS_DIR}' appears empty; initialising..."
    # repo-add cannot create empty db anymore, do it manually
    bsdtar -cf - -T /dev/null | gzip > "${PKGS_DIR}/qubes.db.tar.gz"
    ln -s qubes.db.tar.gz "${PKGS_DIR}/qubes.db"
    bsdtar -cf - -T /dev/null | gzip > "${PKGS_DIR}/qubes.files.tar.gz"
    ln -s qubes.files.tar.gz "${PKGS_DIR}/qubes.files"
fi

set -e

# Move packages that are in a tree of components (artifacts/repository)
# into a single directory as expected by ArchLinux.
chroot_cmd /bin/sh -c "find . -name '*.pkg.tar.*' -print0 | xargs -0 -I {} mv {} pkgs/"

# Generate custom repository metadata based on packages that are available
# Repo Add need packages to be added in the right version number order as it only keeps the last entered package version
# shellcheck disable=SC2016
chroot_cmd /bin/sh -c 'for pkg in `ls -v pkgs/*.pkg.tar.*`; do repo-add pkgs/qubes.db.tar.gz "$pkg"; done;'

# Ensure pacman doesn't check for disk free space -- it doesn't work in chroots
chroot_cmd sed "s/^ *CheckSpace/#CheckSpace/g" -i /etc/pacman.conf

# Update archlinux keyring first so that Archlinux can be updated even after a long time
chroot_cmd /bin/sh -c \
    "http_proxy='${REPO_PROXY}' pacman -Sy --noconfirm --noprogressbar archlinux-keyring"

# Now update system
chroot_cmd /bin/sh -c \
    "http_proxy='${REPO_PROXY}' pacman -Syu --noconfirm --noprogressbar"
