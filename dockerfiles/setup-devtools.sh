#!/bin/bash

set -eux

# Install devtools for Archlinux
git clone -n https://gitlab.archlinux.org/archlinux/devtools
cd devtools
git checkout 6dd7be3fd4d3104101f5a8bbf0f12fcfe8124fd7
make install DESTDIR=/ PREFIX=/usr/local
ln -s /usr/local/bin/archbuild /usr/local/bin/qubes-x86_64-build
