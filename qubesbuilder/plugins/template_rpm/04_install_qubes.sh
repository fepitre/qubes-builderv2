#!/bin/bash
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2015 Marek Marczykowski-Górecki <marmarek@invisiblethingslab.com>
# Copyright (C) 2017 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
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

cp "${TEMPLATE_CONTENT_DIR}/template-builder-repo-${DIST_NAME}.repo" "${INSTALL_DIR}/etc/yum.repos.d/"
if [ -n "$USE_QUBES_REPO_VERSION" ]; then
    sed -e "s/%QUBESVER%/$USE_QUBES_REPO_VERSION/g" \
        -e "s/\$sysroot//g" \
        < "${PLUGINS_DIR}/source_rpm/repos/qubes-repo-vm-${DIST_NAME}.repo" \
        > "${INSTALL_DIR}/etc/yum.repos.d/template-qubes-vm.repo"
    if [ -n "$QUBES_MIRROR" ]; then
        sed -i "s#baseurl.*yum.qubes-os.org#baseurl = $QUBES_MIRROR#" "${INSTALL_DIR}/etc/yum.repos.d/template-qubes-vm.repo"
    fi
    keypath="${PLUGINS_DIR}/source_rpm/keys/qubes-release-${USE_QUBES_REPO_VERSION}-signing-key.asc"
    if [ -r "$keypath" ]; then
        # use stdin to not copy the file into chroot. /dev/stdin
        # symlink doesn't exists there yet
        chroot_cmd rpm --import /proc/self/fd/0 < "$keypath"
        # for DNF to be able to verify metadata too, the file must be copied anyway :/
        cp "$keypath" "${INSTALL_DIR}/etc/pki/rpm-gpg/RPM-GPG-KEY-qubes-${USE_QUBES_REPO_VERSION}-primary"
    fi
    if [ "${DIST_NAME}" = "centos-stream" ]; then
        key_dist=centos
    else
        key_dist="${DIST_NAME}"
    fi
    keypath="${PLUGINS_DIR}/source_rpm/keys/RPM-GPG-KEY-qubes-${USE_QUBES_REPO_VERSION}-${key_dist}"
    if [ -r "$keypath" ]; then
        # use stdin to not copy the file into chroot. /dev/stdin
        # symlink doesn't exists there yet
        chroot_cmd rpm --import /proc/self/fd/0 < "$keypath"
        # for DNF to be able to verify metadata too, the file must be copied anyway :/
        cp "$keypath" "${INSTALL_DIR}/etc/pki/rpm-gpg/"
    fi
    if [ "0$USE_QUBES_REPO_TESTING" -gt 0 ]; then
        yumConfigRepository enable 'qubes-builder-*-current-testing'
    fi
fi

echo "--> Installing RPMs..."
if [ "x$TEMPLATE_FLAVOR" != "x" ]; then
    installPackages "packages_qubes_${TEMPLATE_FLAVOR}.list" || RETCODE=1
else
    installPackages packages_qubes.list || RETCODE=1
fi

chroot_cmd sh -c 'rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-qubes-*'

# WIP: currently limit to Fedora the add_3rd_party_software.sh
if [ "${DIST_NAME}" == "fedora" ]; then
    if [ "$TEMPLATE_FLAVOR" != "minimal" ] && ! elementIn 'no-third-party' "${TEMPLATE_OPTIONS[@]}"; then
        echo "--> Installing 3rd party apps"
        "${TEMPLATE_CONTENT_DIR}/add_3rd_party_software.sh" || RETCODE=1
    fi
fi

if ! grep -q LANG= "${INSTALL_DIR}/etc/locale.conf" 2>/dev/null; then
    if [ "${DIST_NAME}" == "fedora" ]; then
        echo "LANG=C.UTF-8" >> "${INSTALL_DIR}/etc/locale.conf"
    fi
    if [ "${DIST_NAME}" == "centos-stream" ] || [ "${DIST_NAME}" == "centos" ]; then
        echo "LANG=en_US.UTF-8" >> "${INSTALL_DIR}/etc/locale.conf"
    fi
fi

if ! containsFlavor "minimal" && [ "0$TEMPLATE_ROOT_WITH_PARTITIONS" -eq 1 ]; then
    chroot_cmd mount -t sysfs sys /sys
    chroot_cmd mount -t devtmpfs none /dev
    # find the right loop device, _not_ its partition
    dev=$(df --output=source "$INSTALL_DIR" | tail -n 1)
    dev=${dev%p?}
    # if root.img have partitions, install kernel and grub there
    yumInstall kernel || RETCODE=1
    yumInstall grub2 qubes-kernel-vm-support || RETCODE=1
    if [ -x "$INSTALL_DIR/usr/sbin/dkms" ]; then
        yumInstall make || RETCODE=1
        for kver in "${INSTALL_DIR}"/lib/modules/*
        do
            kver="$(basename "$kver")"
            yumInstall "kernel-devel-${kver}" || RETCODE=1
            chroot_cmd dkms autoinstall -k "$kver" || RETCODE=1
        done
    fi
    for kver in "${INSTALL_DIR}"/lib/modules/*
    do
        kver="$(basename "$kver")"
        chroot_cmd dracut -f -a "qubes-vm" \
            "/boot/initramfs-${kver}.img" "${kver}" || RETCODE=1
    done
    chroot_cmd grub2-install --target=i386-pc "$dev" || RETCODE=1
    chroot_cmd grub2-mkconfig -o /boot/grub2/grub.cfg || RETCODE=1
    fuser -vm /builder/mnt
    fuser -kMm /builder/mnt
    fuser -vm /builder/mnt
    chroot_cmd umount /sys /dev
fi

# Distribution specific steps
buildStep "${0}" "${DIST_CODENAME}"

rm -f "${INSTALL_DIR}/etc/yum.repos.d/template-builder-repo-${DIST_NAME}.repo"
rm -f "${INSTALL_DIR}/etc/yum.repos.d/template-qubes-vm.repo"

exit $RETCODE
