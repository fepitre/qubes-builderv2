#!/bin/bash

set -eux

# Install dependencies for Qubes Builder
apt-get update
apt-get install -y sudo curl debootstrap devscripts dpkg-dev \
    git wget python3-debian e2fsprogs pbuilder tree reprepro \
    psutils fdisk udev rpm tree pacman m4 asciidoc python3-jinja2
apt-get clean all

# Create build user
useradd -m user
usermod -aG sudo user && echo '%sudo ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/sudo
