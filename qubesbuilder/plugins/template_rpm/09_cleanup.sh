#!/bin/bash

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
