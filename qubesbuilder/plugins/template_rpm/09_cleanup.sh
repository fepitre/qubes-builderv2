#!/bin/bash
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2015 Marek Marczykowski-Górecki <marmarek@invisiblethingslab.com>
# Copyright (C) 2021 Ivan Kardykov <kardykov@tabit.pro>
# Copyright (C) 2022 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
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
# SPDX-License-Identifier: GPL-3.0-or-later

rm -f "${INSTALL_DIR}"/var/lib/rpm/__db.00* "${INSTALL_DIR}"/var/lib/rpm/.rpm.lock
rm -f "${INSTALL_DIR}"/var/lib/systemd/random-seed
rm -rf "${INSTALL_DIR}"/var/log/journal/*

dnf -c "${PLUGINS_DIR}/source_rpm/dnf/template-dnf-${DIST_NAME}.conf" "${DNF_OPTS[@]}" clean packages --installroot="${INSTALL_DIR}"

# Make sure that rpm database has right format (for rpm version in template, not host)
echo "--> Rebuilding rpm database..."
chroot "${INSTALL_DIR}" /bin/rpm --rebuilddb 2> /dev/null

if [ -x "${INSTALL_DIR}"/usr/bin/dnf ]; then
    chroot "${INSTALL_DIR}" dnf clean all
    # if dnf is used, remove yum cache completely
    rm -rf "${INSTALL_DIR}"/var/cache/yum/* || :
fi

truncate --no-create --size=0 "${INSTALL_DIR}"/var/log/dnf.*

exit 0
