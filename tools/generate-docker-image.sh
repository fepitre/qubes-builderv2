#!/bin/bash

set -ex

if [ $# -ne 1 ]; then
    echo "Usage: $0 <MOCK_CONFIGURATION_FILE>" >&2
    exit 1
fi

MOCK_CONF="$1"
MOCK_CONF_BN="$(basename "$MOCK_CONF")"

[ -n "$MOCK_CONF" ] || {
    echo "Please provide non empty mock configuration file."
    exit 1
}

TOOLS_DIR="$(readlink -f "$(dirname "$0")")"

# Remove chroot and cache
sudo mock \
    -r "$MOCK_CONF" \
    --scrub=all

# Create Mock chroot cache
sudo mock \
    -r "$MOCK_CONF" \
    --init \
    --no-bootstrap-chroot \
    --config-opts chroot_setup_cmd='install dnf @buildsys-build'

# Create Docker image
# FIXME: The trim of .cfg extension does not work if rawhide is provided implicitly
#  like at the time of writing 'fedora-37-x86_64'. We need to find a more reliable way
#  to obtain mock chroot name.
sudo docker build \
    -f "${TOOLS_DIR}/../dockerfiles/fedora.Dockerfile" \
    -t qubes-builder-fedora \
    "/var/cache/mock/${MOCK_CONF_BN%.cfg}/root_cache/"
