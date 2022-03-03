#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

if [ "$DEBUG" == "1" ]; then
    set -x
fi

source "${TEMPLATE_CONTENT_DIR}/vars.sh"
source "${TEMPLATE_CONTENT_DIR}/distribution.sh"

##### '=========================================================================
debug ' Cleaning up...'
##### '=========================================================================

# ==============================================================================
# Execute any template flavor or sub flavor 'pre' scripts
# ==============================================================================
buildStep "${0}" "pre"

#### '-------------------------------------------------------------------------
info ' Cleaning up  any left over files from installation'
#### '-------------------------------------------------------------------------
rm -rf "${INSTALL_DIR}/var/cache/apt/archives"
rm -rf "${INSTALL_DIR}/var/cache/apt/pkgcache.bin"
rm -rf "${INSTALL_DIR}/var/cache/apt/srcpkgcache.bin"
rm -f "${INSTALL_DIR}/etc/apt/sources.list.d/qubes-builder.list"
rm -rf "${INSTALL_DIR}/${TMPDIR}"
rm -f "${INSTALL_DIR}/var/lib/systemd/random-seed"
sed -i "s/$(hostname)/${DIST_NAME}/"  "${INSTALL_DIR}/etc/hosts" || true

# ==============================================================================
# Execute any template flavor or sub flavor 'post' scripts
# ==============================================================================
buildStep "${0}" "post"
