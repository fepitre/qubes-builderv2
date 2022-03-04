#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

## Copyright (C) 2012 - 2021 ENCRYPTED SUPPORT LP <adrelanos@whonix.org>
## See the file COPYING for copying conditions.

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
