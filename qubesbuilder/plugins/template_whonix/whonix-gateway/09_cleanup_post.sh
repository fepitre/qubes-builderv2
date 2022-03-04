#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2015-2021 Patrick Schleizer <adrelanos@whonix.org>
# Copyright (C) 2015 Jason Mehring <nrgaway@gmail.com>
# Copyright (C) 2022 Frédéric Pierret <frederic@invisiblethingslab.com>
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


if [ "$VERBOSE" -ge 2 -o "$DEBUG" == "1" ]; then
    set -x
fi

source "${SCRIPTSDIR}/vars.sh"
source "${SCRIPTSDIR}/distribution.sh"

##### '-------------------------------------------------------------------------
debug ' Whonix post installation cleanup'
##### '-------------------------------------------------------------------------

## Qubes R3.1 compatibility.
## Can be removed on Qubes R3.2 and above.
## https://github.com/QubesOS/qubes-issues/issues/1174
if [ "$(type -t chroot_cmd)" = "function" ]; then
   chroot_cmd="chroot_cmd"
else
   chroot_cmd="chroot"
fi

if [ -x "${INSTALLDIR}/usr/lib/anon-dist/chroot-scripts-post.d/80_cleanup" ]; then
   $chroot_cmd "/usr/lib/anon-dist/chroot-scripts-post.d/80_cleanup"
fi
