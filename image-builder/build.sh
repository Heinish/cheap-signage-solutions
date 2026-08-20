#!/bin/bash -e
# Builds the CSS signage image with pi-gen. Requires Docker (pi-gen's
# build-docker.sh runs the whole build inside a privileged container, so
# you don't need debootstrap/qemu-user-static/binfmt set up on the host -
# just Docker itself, e.g. Docker Desktop with WSL2 on Windows, or native
# Docker on Linux/Mac).
#
# Usage: ./build.sh [pi-gen-ref]
#   pi-gen-ref  git ref of RPi-Distro/pi-gen to build against (default below)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PI_GEN_REF="${1:-bookworm}"
WORK_DIR="${SCRIPT_DIR}/.pi-gen-src"
OUTPUT_DIR="${SCRIPT_DIR}/output"

echo "==> Fetching pi-gen (${PI_GEN_REF})"
if [ -d "${WORK_DIR}" ]; then
    git -C "${WORK_DIR}" fetch origin "${PI_GEN_REF}"
    git -C "${WORK_DIR}" checkout "${PI_GEN_REF}"
else
    git clone --branch "${PI_GEN_REF}" --depth 1 https://github.com/RPi-Distro/pi-gen.git "${WORK_DIR}"
fi

echo "==> Laying in the CSS custom stage"
rm -rf "${WORK_DIR}/stage-css"
cp -r "${SCRIPT_DIR}/stage-css" "${WORK_DIR}/stage-css"
cp "${SCRIPT_DIR}/config" "${WORK_DIR}/config"

echo "==> Building (this takes a while - full Debian bootstrap + package installs)"
cd "${WORK_DIR}"
CONTINUE=${CONTINUE:-0} ./build-docker.sh

echo "==> Collecting output"
mkdir -p "${OUTPUT_DIR}"
cp -v "${WORK_DIR}"/deploy/*css-signage*.img.xz "${OUTPUT_DIR}/" 2>/dev/null || \
    echo "No css-signage image found in deploy/ - check the build log above for the failing stage."

echo "==> Done. Output in ${OUTPUT_DIR}"
