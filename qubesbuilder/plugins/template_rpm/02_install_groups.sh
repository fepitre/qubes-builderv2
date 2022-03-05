#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2015 Marek Marczykowski-Górecki <marmarek@invisiblethingslab.com>
# Copyright (C) 2020 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
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

# shellcheck source=qubesbuilder/plugins/template_rpm/distribution.sh
source "${TEMPLATE_CONTENT_DIR}/distribution.sh"

# Prepare system mount points
prepareChroot

#### '----------------------------------------------------------------------
info ' Trap ERR and EXIT signals and cleanup (umount)'
#### '----------------------------------------------------------------------
trap cleanup ERR
trap cleanup EXIT

#### '----------------------------------------------------------------------
info ' Distribution specific steps (install systemd, add sources, etc)'
#### '----------------------------------------------------------------------
buildStep "$0" "${DIST_CODENAME}"

#### '----------------------------------------------------------------------
info " Installing extra packages from packages.list file"
#### '----------------------------------------------------------------------
chroot_cmd "${DNF}" clean all
# shellcheck disable=SC2119
installPackages
# shellcheck disable=SC2119
yumUpdate

#### '----------------------------------------------------------------------
info ' Cleanup'
#### '----------------------------------------------------------------------
trap - ERR EXIT
trap
