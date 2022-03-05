#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

if [ "$DEBUG" == "1" ]; then
    set -x
fi

# shellcheck source=qubesbuilder/plugins/template_debian/vars.sh
source "${PLUGINS_DIR}/template_debian/vars.sh"
# shellcheck source=qubesbuilder/plugins/template_debian/distribution.sh
source "${PLUGINS_DIR}/template_debian/distribution.sh"

##### "=========================================================================
debug " Configuring and Installing packages for ${DIST_CODENAME}"
##### "=========================================================================

# If .prepared_debootstrap has not been completed, don't continue
exitOnNoFile "${INSTALL_DIR}/${TMPDIR}/.prepared_debootstrap" "prepared_debootstrap installation has not completed!... Exiting"

# Create system mount points
prepareChroot

# Make sure there is a resolv.conf with network of this AppVM for building
createResolvConf

# ==============================================================================
# Execute any template flavor or sub flavor 'pre' scripts
# ==============================================================================
buildStep "${0}" "pre"

# ==============================================================================
# Configure base system and install any additional packages which could
# include +TEMPLATE_FLAVOR such as gnome as set in configuration file
# ==============================================================================
#### '----------------------------------------------------------------------
info ' Trap ERR and EXIT signals and cleanup (umount)'
#### '----------------------------------------------------------------------
trap cleanup ERR
trap cleanup EXIT

#### '----------------------------------------------------------------------
info ' Install standard Debian packages'
#### '----------------------------------------------------------------------
containsFlavor "minimal" || {
    read -r -a packages <<<"$(chroot_cmd tasksel --new-install --task-packages standard)"
    # media-types : Breaks: mime-support (<= 3.64) but 3.64 is to be installed
    read -r -a packages <<<"${packages[@]//media-types/}"
    if [ -n "$eatmydata_maybe" ]; then
        # shellcheck disable=SC2097,2098
        eatmydata_maybe="" aptInstall "$eatmydata_maybe"
    fi
    aptInstall "${packages[@]}"
}

#### '----------------------------------------------------------------------
info ' Distribution specific steps (install systemd, add sources, etc)'
#### '----------------------------------------------------------------------
buildStep "$0" "${DIST_CODENAME}"

#### '----------------------------------------------------------------------
info " Installing extra packages in script_${DIST_CODENAME}/packages.list file"
#### '----------------------------------------------------------------------
# shellcheck disable=SC2119
installPackages
createSnapshot "packages"
touch "${INSTALL_DIR}/${TMPDIR}/.prepared_packages"

#### '----------------------------------------------------------------------
info ' Execute any template flavor or sub flavor scripts after packages are installed'
#### '----------------------------------------------------------------------
buildStep "$0" "packages_installed"

#### '----------------------------------------------------------------------
info ' apt-get dist-upgrade'
#### '----------------------------------------------------------------------
aptDistUpgrade

#### '----------------------------------------------------------------------
info ' Cleanup'
#### '----------------------------------------------------------------------
touch "${INSTALL_DIR}/${TMPDIR}/.prepared_groups"
trap - ERR EXIT
trap

# ==============================================================================
# Execute any template flavor or sub flavor 'post' scripts
# ==============================================================================
buildStep "${0}" "post"

# ==============================================================================
# Kill all processes and umount all mounts within ${INSTALL_DIR}, but not
# ${INSTALL_DIR} itself (extra '/' prevents ${INSTALL_DIR} from being umounted)
# ==============================================================================
umount_all "${INSTALL_DIR}/" || true
