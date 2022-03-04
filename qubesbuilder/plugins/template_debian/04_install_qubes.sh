#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

if [ "$DEBUG" == "1" ]; then
    set -x
fi

source "${PLUGINS_DIR}/template_debian/vars.sh"
source "${PLUGINS_DIR}/template_debian/distribution.sh"

##### '-------------------------------------------------------------------------
debug ' Installing Qubes packages'
##### '-------------------------------------------------------------------------

# If .prepared_debootstrap has not been completed, don't continue
exitOnNoFile "${INSTALL_DIR}/${TMPDIR}/.prepared_groups" "prepared_groups installataion has not completed!... Exiting"

# Create system mount points
prepareChroot

# ==============================================================================
# Execute any template flavor or sub flavor 'pre' scripts
# ==============================================================================
buildStep "${0}" "pre"

if ! [ -f "${INSTALL_DIR}/${TMPDIR}/.prepared_qubes" ]; then
    #### '----------------------------------------------------------------------
    info ' Trap ERR and EXIT signals and cleanup (umount)'
    #### '----------------------------------------------------------------------
    trap cleanup ERR
    trap cleanup EXIT

    #### '----------------------------------------------------------------------
    info ' Install Qubes Repo and update'
    #### '----------------------------------------------------------------------
    installQubesRepo
    aptUpdate

    #### '----------------------------------------------------------------------
    info ' Execute any distribution specific flavor or sub flavor'
    #### '----------------------------------------------------------------------
    buildStep "${0}" "${DIST_CODENAME}"

    #### '----------------------------------------------------------------------
    info ' Install Qubes packages listed in packages_qubes.list file(s)'
    #### '----------------------------------------------------------------------
    installPackages packages_qubes.list

    if ! containsFlavor "minimal" && [ "0$TEMPLATE_ROOT_WITH_PARTITIONS" -eq 1 ]; then
        #### '------------------------------------------------------------------
        info ' Install kernel and bootloader'
        #### '------------------------------------------------------------------
        aptInstall qubes-kernel-vm-support
        aptInstall "${KERNEL_PACKAGE_NAME}"
        aptInstall grub-pc
        # find the right loop device, _not_ its partition
        dev=$(df --output=source $INSTALL_DIR | tail -n 1)
        dev=${dev%p?}
        chroot_cmd mount -t devtmpfs none /dev
        chroot_cmd grub-install --target=i386-pc --modules=part_gpt "$dev"
        echo "grub-pc grub-pc/install_devices multiselect /dev/xvda" |\
            chroot_cmd debconf-set-selections
        chroot_cmd update-grub2
    fi

    uninstallQubesRepo

    #### '----------------------------------------------------------------------
    info ' Re-update locales'
    ####   (Locales get reset during package installation sometimes)
    #### '----------------------------------------------------------------------
    updateLocale

    #### '----------------------------------------------------------------------
    info ' Default applications fixup'
    #### '----------------------------------------------------------------------
    setDefaultApplications

    #### '----------------------------------------------------------------------
    info ' Cleanup'
    #### '----------------------------------------------------------------------
    umount_all "${INSTALL_DIR}/" || true
    touch "${INSTALL_DIR}/${TMPDIR}/.prepared_qubes"
    trap - ERR EXIT
    trap
fi

# ==============================================================================
# Execute any template flavor or sub flavor 'post' scripts
# ==============================================================================
buildStep "${0}" "post"

# ==============================================================================
# Kill all processes and umount all mounts within ${INSTALL_DIR}, but not
# ${INSTALL_DIR} itself (extra '/' prevents ${INSTALL_DIR} from being umounted)
# ==============================================================================
umount_all "${INSTALL_DIR}/" || true
