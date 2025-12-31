#!/bin/bash

set -ex

if [ $# -lt 1 ]; then
    echo "Usage: $0 CONTAINER_ENGINE <MOCK_CONFIGURATION_FILE>" >&2
    echo "If MOCK_CONFIGURATION_FILE is provided, it will use Mock chroot as container rootfs." >&2
    exit 1
fi

CONTAINER_ENGINE="$1"
MOCK_CONF="$2"

[ -n "$CONTAINER_ENGINE" ] || {
    echo "Please provide container engine: 'docker' or 'podman'."
    exit 1
}

if [ "$CONTAINER_ENGINE" == "docker" ]; then
    CONTAINER_CMD="sudo docker"
elif [ "$CONTAINER_ENGINE" == "podman" ]; then
    CONTAINER_CMD="podman"
else
    echo "Only 'docker' and 'podman' are supported."
    exit 1
fi

TOOLS_DIR="$(dirname "$0")"
TOOLS_DIR="$(readlink -f "$TOOLS_DIR")"

if [ -n "$MOCK_CONF" ]; then
    MOCK_CONF_BN="$(basename "$MOCK_CONF")"

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
    $CONTAINER_CMD build \
        -f "${TOOLS_DIR}/../dockerfiles/fedora-mock.Dockerfile" \
        -t qubes-builder-fedora \
        "/var/cache/mock/${MOCK_CONF_BN%.cfg}/root_cache/"
else
    $CONTAINER_CMD build \
        -f "${TOOLS_DIR}/../dockerfiles/fedora.Dockerfile" \
        -t qubes-builder-fedora .
fi
