#!/bin/bash -e

# When updating the version, you must update the SHA512/256 sum as well, e.g.:
# shasum -a 512256 "${ARCHIVE}" > "${ARCHIVE}.sum"
VERSION=v0.4.7
ARCHIVE="shellcheck-${VERSION}.linux.x86_64.tar.xz"
URL="https://storage.googleapis.com/shellcheck/${ARCHIVE}"
SUMFILE="${ARCHIVE}.sum"

die() {
  echo "$1"
  exit 1
}

[ -f "${SUMFILE}" ] || \
  die "Missing integrity file ${SUMFILE}! (wrong directory?)"

echo "Downloading ${URL} ..."
curl "${URL}" -o "${ARCHIVE}"
echo

echo "Checking archive integrity..."
shasum -a 512256 -c "${SUMFILE}" || die "Integrity check failed!"
echo

echo "Extracting shellcheck binary..."
# NOTE: Transforms shellcheck-<version>/ to bin/shellcheck/.
tar --xz -xf "${ARCHIVE}" "${BINARY_PATH}" \
  --transform="s|shellcheck-${VERSION}|bin/shellcheck|"
