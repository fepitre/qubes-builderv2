#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

source "${TEMPLATE_CONTENT_DIR}/vars.sh"
source "${TEMPLATE_CONTENT_DIR}/distribution.sh"

#### '----------------------------------------------------------------------
info ' Installing flash plugin'
#### '----------------------------------------------------------------------
aptInstall flashplugin-nonfree
