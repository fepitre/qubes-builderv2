#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

# shellcheck source=qubesbuilder/plugins/template_rpm/distribution.sh
source "${TEMPLATE_CONTENT_DIR}/distribution.sh"

#### '----------------------------------------------------------------------
info ' Trap ERR and EXIT signals and cleanup (umount)'
#### '----------------------------------------------------------------------
trap cleanup ERR EXIT

#### '----------------------------------------------------------------------
info ' Copying 3rd party software to "tmp" directory to prepare for installation'
#### '----------------------------------------------------------------------
cp -a "${TEMPLATE_CONTENT_DIR}/3rd_party_software" "${INSTALL_DIR}/tmp"

#### '----------------------------------------------------------------------
info ' Installing google-chrome repos'
#### '----------------------------------------------------------------------

# Google Chrome
# =============
# Key Details:
# - Download: https://dl-ssl.google.com/linux/linux_signing_key.pub
# - Key ID: Google, Inc. Linux Package Signing Key <linux-packages-keymaster@google.com>
# - Fingerprint: 4CCA 1EAF 950C EE4A B839 76DC A040 830F 7FAC 5991
#
# sudo rpm --import linux_signing_key.pub
#
# You can verify the key installation by running:
# - rpm -qi gpg-pubkey-7fac5991-*
#
# To manually verify an RPM package, you can run the command:
# - rpm --checksig -v packagename.rpm
#

install -m 0644 "${TEMPLATE_CONTENT_DIR}/3rd_party_software/google-linux_signing_key.pub" "${INSTALL_DIR}/etc/pki/rpm-gpg/"
cat << EOF > "${INSTALL_DIR}/etc/yum.repos.d/google-chrome.repo"
[google-chrome]
name=google-chrome - \$basearch
baseurl=http://dl.google.com/linux/chrome/rpm/stable/\$basearch
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/google-linux_signing_key.pub
EOF
chmod 644 "${INSTALL_DIR}/etc/yum.repos.d/google-chrome.repo"

#### '----------------------------------------------------------------------
info ' Installing adobe repo'
#### '----------------------------------------------------------------------
yumInstall /tmp/3rd_party_software/adobe-release-x86_64.noarch.rpm

if [ "$TEMPLATE_FLAVOR" == "fullyloaded" ]; then
    #### '------------------------------------------------------------------
    info ' Installing 3rd party software'
    #### '------------------------------------------------------------------
    yumInstall google-chrome-stable
    yumInstall flash-plugin
else
    yumConfigRepository disable google-chrome > /dev/null
    yumConfigRepository disable adobe-linux-x86_64 > /dev/null
fi


#### '----------------------------------------------------------------------
info ' Installing rpmfusion-free repos'
#### '----------------------------------------------------------------------
if [ -e "${INSTALL_DIR}/tmp/3rd_party_software/rpmfusion-free-release-${DIST_VER}.noarch.rpm" ]; then
    yumInstall "/tmp/3rd_party_software/rpmfusion-free-release-${DIST_VER}.noarch.rpm"

    # Disable rpmfusion-free repos
    yumConfigRepository disable rpmfusion-free > /dev/null
    yumConfigRepository disable rpmfusion-free-debuginfo > /dev/null
    yumConfigRepository disable rpmfusion-free-source > /dev/null
    yumConfigRepository disable rpmfusion-free-updates > /dev/null
    yumConfigRepository disable rpmfusion-free-updates-debuginfo > /dev/null
    yumConfigRepository disable rpmfusion-free-updates-source > /dev/null
    yumConfigRepository disable rpmfusion-free-updates-testing > /dev/null
    yumConfigRepository disable rpmfusion-free-updates-testing-debuginfo > /dev/null
    yumConfigRepository disable rpmfusion-free-updates-testing-source > /dev/null
else
    error "rpmfusion-free-release-${DIST_VER}.noarch.rpm not found!"
    exit 1
fi

#### '----------------------------------------------------------------------
info ' Installing rpmfusion-nonfree repos'
#### '----------------------------------------------------------------------
if [ -e "${INSTALL_DIR}/tmp/3rd_party_software/rpmfusion-nonfree-release-${DIST_VER}.noarch.rpm" ]; then
    yumInstall "/tmp/3rd_party_software/rpmfusion-nonfree-release-${DIST_VER}.noarch.rpm"

    # Disable rpmfusion-nonfree repos
    yumConfigRepository disable rpmfusion-nonfree > /dev/null
    yumConfigRepository disable rpmfusion-nonfree-debuginfo > /dev/null
    yumConfigRepository disable rpmfusion-nonfree-source > /dev/null
    yumConfigRepository disable rpmfusion-nonfree-updates > /dev/null
    yumConfigRepository disable rpmfusion-nonfree-updates-debuginfo > /dev/null
    yumConfigRepository disable rpmfusion-nonfree-updates-source > /dev/null
    yumConfigRepository disable rpmfusion-nonfree-updates-testing > /dev/null
    yumConfigRepository disable rpmfusion-nonfree-updates-testing-debuginfo > /dev/null
    yumConfigRepository disable rpmfusion-nonfree-updates-testing-source > /dev/null
else
    error "rpmfusion-nonfree-release-${DIST_VER}.noarch.rpm not found!"
    exit 1
fi

#### '----------------------------------------------------------------------
info ' Cleanup'
#### '----------------------------------------------------------------------
rm -rf "${INSTALL_DIR}/tmp/3rd_party_software"
trap - ERR EXIT
trap
