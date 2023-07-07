#!/bin/bash

set -ex -o pipefail

# Check if chroot archive does not contain input files

elementIn () {
  local element
  for element in "${@:2}"; do [[ "$element" == "$1" ]] && return 0; done
  return 1
}

ARTIFACTS_DIR="$(readlink -f "$1")"
DIST="$2"
shift 2
read -r -a FILES <<< "$@"

# Remove prefix for vm- and host-
DIST="${DIST#vm-}"
DIST="${DIST#host-}"

if elementIn "${DIST}" bullseye bookworm trixie; then
    CHROOT_ARCHIVE="${ARTIFACTS_DIR}/cache/chroot/${DIST}/pbuilder/base.tgz"
elif [[ "${DIST}" =~ fc[1-9]+ ]]; then
    # FIXME: fragile method to determine mock directory name
    CHROOT_ARCHIVE="${ARTIFACTS_DIR}/cache/chroot/${DIST}/mock/fedora-${DIST#fc-}-x86_64/root_cache/cache.tar.gz"
else
    echo "ERROR: unsupported distribution '${DIST}'."
    exit 1
fi

for f in "${FILES[@]}"; do
    if tar tf "${CHROOT_ARCHIVE}" ".$f" 2>/dev/null; then
        echo "ERROR: found '$f'."
        exit 1
    fi
done
