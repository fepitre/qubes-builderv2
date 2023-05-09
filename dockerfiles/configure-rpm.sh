#!/bin/bash

set -eux

# Install dependencies for Qubes Builder
dnf -y update
dnf install -y createrepo_c debootstrap devscripts dpkg-dev git mock pbuilder \
    which perl-Digest-MD5 perl-Digest-SHA python3-pyyaml e2fsprogs \
    python3-sh rpm-build rpmdevtools wget python3-debian reprepro systemd-udev \
    tree python3-jinja2-cli pacman m4 asciidoc rsync psmisc zstd
dnf clean all

# Create build user
useradd -m user
usermod -aG wheel user && echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/wheel
