#!/bin/sh

# Prepare local builder repository

cd "${PACKAGES_DIR}" && createrepo_c -g "${TEMPLATE_CONTENT_DIR}/comps-qubes-template.xml" .
chown -R --reference="${PACKAGES_DIR}" "${PACKAGES_DIR}"
