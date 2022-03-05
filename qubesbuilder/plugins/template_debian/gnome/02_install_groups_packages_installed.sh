#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

# shellcheck source=qubesbuilder/plugins/template_debian/vars.sh
source "${PLUGINS_DIR}/template_debian/vars.sh"
# shellcheck source=qubesbuilder/plugins/template_debian/distribution.sh
source "${PLUGINS_DIR}/template_debian/distribution.sh"

#### '----------------------------------------------------------------------
info ' Installing Gnome'
#### '----------------------------------------------------------------------
#packages="$(chroot_cmd tasksel --new-install --task-packages desktop)"
#packages+=" $(chroot_cmd tasksel --new-install --task-packages gnome-desktop)"
read -r -a packages <<<"$(chroot_cmd tasksel --new-install --task-packages gnome-desktop)"
aptInstall "${packages[@]}"
