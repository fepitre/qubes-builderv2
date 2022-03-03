#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

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
installPackages
yumUpdate

#### '----------------------------------------------------------------------
info ' Cleanup'
#### '----------------------------------------------------------------------
trap - ERR EXIT
trap
