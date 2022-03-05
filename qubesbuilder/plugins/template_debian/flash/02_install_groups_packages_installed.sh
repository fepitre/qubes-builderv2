#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

# shellcheck source=qubesbuilder/plugins/template_debian/vars.sh
source "${PLUGINS_DIR}/template_debian/vars.sh"
# shellcheck source=qubesbuilder/plugins/template_debian/distribution.sh
source "${PLUGINS_DIR}/template_debian/distribution.sh"

#### '----------------------------------------------------------------------
info ' Installing flash plugin'
#### '----------------------------------------------------------------------
aptInstall flashplugin-nonfree
