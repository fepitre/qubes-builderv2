#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

## Copyright (C) 2012 - 2021 ENCRYPTED SUPPORT LP <adrelanos@whonix.org>
## See the file COPYING for copying conditions.

if [ "$DEBUG" == "1" ]; then
    set -x
fi

# Source external scripts
source "${PLUGINS_DIR}/template_debian/vars.sh"
source "${PLUGINS_DIR}/template_debian/distribution.sh"

## If .prepared_debootstrap has not been completed, don't continue.
exitOnNoFile "${INSTALL_DIR}/${TMPDIR}/.prepared_qubes" "prepared_qubes installation has not completed!... Exiting"

#### '--------------------------------------------------------------------------
info ' Trap ERR and EXIT signals and cleanup (umount)'
#### '--------------------------------------------------------------------------
trap cleanup ERR
trap cleanup EXIT

prepareChroot

mount --bind /dev "${INSTALL_DIR}/dev"

aptInstall apt-transport-https
aptInstall apt-transport-tor

## Install Qubes' repository so dependencies of the qubes-whonix package
## that gets installed by Whonix's build script will be available.
## (Cant be done in '.whonix_prepared', because installQubesRepo's 'mount' does not survive reboots.)
installQubesRepo

## Debugging.
env

## https://github.com/QubesOS/qubes-issues/issues/4957
#[ -n "$whonix_repository_uri" ] || whonix_repository_uri="tor+http://deb.dds6qkxpwdeubwucdiaord2xgbbeyds25rbsgr73tbfpqpt4a6vjwsyd.onion"
[ -n "$whonix_repository_uri" ] || whonix_repository_uri="https://deb.whonix.org"

## Better to build from bullseye-testers to test the upgrades.
[ -n "$whonix_repository_suite" ] || whonix_repository_suite="bullseye-testers"
[ -n "$whonix_signing_key_fingerprint" ] || whonix_signing_key_fingerprint="916B8D99C38EAF5E8ADC7A2A8D66066A2EEACCDA"
[ -n "$whonix_signing_key_file" ] || whonix_signing_key_file="${PLUGINS_DIR}/template_whonix/keys/whonix-developer-patrick.asc"
[ -n "$gpg_keyserver" ] || gpg_keyserver="keys.gnupg.net"
[ -n "$whonix_repository_components" ] || whonix_repository_components="main"
[ -n "$whonix_repository_apt_line" ] || whonix_repository_apt_line="deb [signed-by=/usr/share/keyrings/derivative.asc] $whonix_repository_uri $whonix_repository_suite $whonix_repository_components"
[ -n "$whonix_repository_temporary_apt_sources_list" ] || whonix_repository_temporary_apt_sources_list="/etc/apt/sources.list.d/whonix_build.list"
[ -n "$apt_target_key" ] || apt_target_key="/usr/share/keyrings/derivative.asc"

if [ "${TEMPLATE_FLAVOR}" = "whonix-gateway" ]; then
   [ -n "$whonix_meta_package_to_install" ] || whonix_meta_package_to_install="qubes-whonix-gateway"
elif [ "${TEMPLATE_FLAVOR}" = "whonix-workstation" ]; then
   [ -n "$whonix_meta_package_to_install" ] || whonix_meta_package_to_install="qubes-whonix-workstation"
else
   error "TEMPLATE_FLAVOR is neither whonix-gateway nor whonix-workstation, it is: ${TEMPLATE_FLAVOR}"
fi

whonix_signing_key_file_name="$(basename "$whonix_signing_key_file")"

if [ "$whonix_signing_key_fingerprint" = "none" ]; then
   info "whonix_signing_key_fingerprint is set to '$whonix_signing_key_fingerprint', therefore not running copying gpg key adding as requested."
else
   ## Debugging.
   test -f "$whonix_signing_key_file"

   cp "$whonix_signing_key_file" "${INSTALL_DIR}/${TMPDIR}/${whonix_signing_key_file_name}"

   ## Debugging.
   chroot_cmd test -f "${TMPDIR}/${whonix_signing_key_file_name}"

   ## https://forums.whonix.org/t/apt-key-deprecation-apt-2-2-changes/11240
   chroot_cmd cp --verbose "${TMPDIR}/${whonix_signing_key_file_name}" "$apt_target_key"

   ## Sanity test. apt-key adv would exit non-zero if not exactly that fingerprint in apt's keyring.
   chroot_cmd apt-key --keyring "$apt_target_key" adv --fingerprint "$whonix_signing_key_fingerprint"
fi

echo "$whonix_repository_apt_line" > "${INSTALL_DIR}/$whonix_repository_temporary_apt_sources_list"

aptUpdate

[ -n "$DEBDEBUG" ] || export DEBDEBUG="1"
[ -n "$tpo_downloader_debug" ] || export tpo_downloader_debug="1"

if [ -n "$WHONIX_TBB_VERSION" ]; then
    mkdir -p "${INSTALL_DIR}/etc/torbrowser.d"
    echo "tbb_version=\"$WHONIX_TBB_VERSION\"" > \
        "${INSTALL_DIR}/etc/torbrowser.d/80_template_builder_override.conf"
fi

aptInstall "$whonix_meta_package_to_install"

uninstallQubesRepo

rm -f "${INSTALL_DIR}/$whonix_repository_temporary_apt_sources_list"

if [ -e "${INSTALL_DIR}/etc/apt/sources.list.d/debian.list" ]; then
    info 'Remove original sources.list (Whonix package anon-apt-sources-list \
ships /etc/apt/sources.list.d/debian.list)'
    rm -f "${INSTALL_DIR}/etc/apt/sources.list"
fi

if [ -n "$WHONIX_TBB_VERSION" ]; then
    # cleanup override after initial install
    rm -f "${INSTALL_DIR}/etc/torbrowser.d/80_template_builder_override.conf"
fi

## Maybe Enable Tor.
if [ "${TEMPLATE_FLAVOR}" == "whonix-gateway" ] && [ "${WHONIX_ENABLE_TOR}" -eq 1 ]; then
    sed -i "s/^#DisableNetwork/DisableNetwork/g" "${INSTALL_DIR}/etc/tor/torrc"
fi

## Workaround for Qubes bug:
## 'Debian Template: rely on existing tool for base image creation'
## https://github.com/QubesOS/qubes-issues/issues/1055
updateLocale

## Workaround. ntpdate needs to be removed here, because it can not be removed from
## template_debian/packages_qubes.list, because that would break minimal Debian templates.
## https://github.com/QubesOS/qubes-issues/issues/1102
UWT_DEV_PASSTHROUGH="1" aptRemove ntpdate || true

UWT_DEV_PASSTHROUGH="1" DEBIAN_FRONTEND="noninteractive" DEBIAN_PRIORITY="critical" DEBCONF_NOWARNINGS="yes" \
    chroot_cmd $eatmydata_maybe apt-get ${APT_GET_OPTIONS} autoremove

## Cleanup.
umount_all "${INSTALL_DIR}/" || true
trap - ERR EXIT
trap
