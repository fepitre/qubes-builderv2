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
debug " Installing custom packages and customizing ${DIST_CODENAME}"
##### "=========================================================================

#### '--------------------------------------------------------------------------
info ' Adding contrib, non-free and Debian security to repository.'
#### '--------------------------------------------------------------------------
updateDebianSourceList
aptUpdate
