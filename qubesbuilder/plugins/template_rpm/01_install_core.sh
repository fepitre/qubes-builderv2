#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

source "${TEMPLATE_CONTENT_DIR}/distribution.sh"

export DNF_OPTS

# bootstrap chroot
"${PLUGINS_DIR}"/source_rpm/scripts/prepare-chroot-base "${INSTALL_DIR}" "${DIST_NAME}" "${DIST_VER}" "${CACHE_DIR}"

# Build the rpmdb again, in case of huge rpm version difference that makes
# rpmdb --rebuilddb doesn't work anymore. Export using rpm from outside
# chroot and import using rpm from within chroot
rpmdb "${RPM_OPTS[@]}" --root="${INSTALL_DIR}" --exportdb > "${CACHE_DIR}/rpmdb.export" || exit 1
rm -rf "${INSTALL_DIR}/var/lib/rpm"
chroot "${INSTALL_DIR}" rpmdb --importdb < "${CACHE_DIR}/rpmdb.export" || exit 1

# remove systemd-resolved symlink
rm -f "${INSTALL_DIR}/etc/resolv.conf"
cp "${TEMPLATE_CONTENT_DIR}/resolv.conf" "${INSTALL_DIR}/etc/"
chmod 644 "${INSTALL_DIR}/etc/resolv.conf"
cp "${TEMPLATE_CONTENT_DIR}/network" "${INSTALL_DIR}/etc/sysconfig/"
chmod 644 "${INSTALL_DIR}/etc/sysconfig/network"
cp -a /dev/null /dev/zero /dev/random /dev/urandom "${INSTALL_DIR}/dev/"

yumInstall "$DNF"
