#!/bin/bash
# Run tests locally exactly as GitLab CI would.
# Usage: ./run-tests.sh [PYTEST_TARGETS]
# Example: ./run-tests.sh "tests/test_check_release_status.py"
#          ./run-tests.sh prepare-cache ~/qb-cache
#          CACHE_ARTIFACTS_DIR=~/qb-cache ./run-tests.sh

set -e

CI_PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

prepare_cache() {
    local cache_dir="${1:-$HOME/qb-cache}"
    local builder_conf="${2:-$CI_PROJECT_DIR/tests/builder-ci.yml}"
    local dists=(host-fc37 vm-bookworm vm-trixie vm-archlinux)

    mkdir -p "$cache_dir"
    echo "Preparing chroot caches into: $cache_dir"
    for dist in "${dists[@]}"; do
        echo "-> init-cache for $dist"
        PYTHONPATH=".:${PYTHONPATH:-}" python3 "$CI_PROJECT_DIR/qb" \
            --builder-conf "$builder_conf" \
            --option "artifacts-dir=$cache_dir" \
            -d "$dist" \
            package init-cache
        echo
    done
}

if [[ "${1:-}" == "prepare-cache" ]]; then
    shift
    prepare_cache "$@"
    exit 0
fi

PYTEST_TARGETS="${*:-tests/}"

PYTEST_ARGS=(
    -vv --color=yes --showlocals
    --tb=long
    --capture=no
    -rA
    -o truncation_limit_chars=0
    -o truncation_limit_lines=0
    -o junit_logging=all
    --junitxml=artifacts/qubesbuilder.xml
)

# Seed chroot caches from a pre-built directory if provided.
if [[ -n "${CACHE_ARTIFACTS_DIR:-}" ]]; then
    PYTEST_ARGS+=(--cache-dir "$CACHE_ARTIFACTS_DIR")
fi

# before_script
mkdir -p "$CI_PROJECT_DIR/artifacts"
mkdir -p ~/results ~/tmp

# script
# shellcheck disable=SC2086
PYTHONPATH=".:${PYTHONPATH:-}" BASE_ARTIFACTS_DIR=~/results TMPDIR=~/tmp \
    pytest-3 "${PYTEST_ARGS[@]}" $PYTEST_TARGETS 2>&1 | tee artifacts/pytest.log
exit "${PIPESTATUS[0]}"
