#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2015 Marek Marczykowski-Górecki <marmarek@invisiblethingslab.com>
# Copyright (C) 2017 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
# Copyright (C) 2021 Demi Marie Obenour <demi@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-late

# shellcheck source=qubesbuilder/plugins/template_rpm/distribution.sh
source "${TEMPLATE_CONTENT_DIR}/distribution.sh"

export DNF_OPTS

# bootstrap chroot
"${PLUGINS_DIR}"/source_rpm/scripts/prepare-chroot-base "${INSTALL_DIR}" "${DIST_NAME}" "${DIST_VER}" "${CACHE_DIR}"

# Build the rpmdb again, in case of huge rpm version difference that makes
# rpmdb --rebuilddb doesn't work anymore. Export using rpm from outside
# chroot and import using rpm from within chroot
rpmdb "${RPM_OPTS[@]}" --root="${INSTALL_DIR}" --exportdb > "${CACHE_DIR}/rpmdb.export" || exit 1
dbpath=$(rpm --eval '%{_dbpath}') || exit 1
new_dbpath=$(chroot "${INSTALL_DIR}" rpm --eval '%{_dbpath}') || exit 1
rm -rf "${INSTALL_DIR}${dbpath}"
rm -rf "${INSTALL_DIR}${new_dbpath}"
chroot "${INSTALL_DIR}" rpmdb --initdb || exit 1
chroot "${INSTALL_DIR}" rpmdb --importdb < "${CACHE_DIR}/rpmdb.export" || exit 1

# remove systemd-resolved symlink
rm -f "${INSTALL_DIR}/etc/resolv.conf"
cp "${TEMPLATE_CONTENT_DIR}/resolv.conf" "${INSTALL_DIR}/etc/"
chmod 644 "${INSTALL_DIR}/etc/resolv.conf"
cp "${TEMPLATE_CONTENT_DIR}/network" "${INSTALL_DIR}/etc/sysconfig/"
chmod 644 "${INSTALL_DIR}/etc/sysconfig/network"
cp -a /dev/null /dev/zero /dev/random /dev/urandom "${INSTALL_DIR}/dev/"

yumInstall "$DNF"
