#!/bin/bash -e

# When updating the version, you must update the SHA512 sum as well, e.g.:
# shasum -a 512 "${ARCHIVE}" > "${ARCHIVE}.sum"
VERSION=0.6.0-r6
SDK_VERSION=2019.06.19.004705
ARCHIVE="shellcheck-${VERSION}.tbz2"
URL="https://storage.googleapis.com/chromeos-prebuilt/host/amd64/amd64-host/chroot-${SDK_VERSION}/packages/dev-util/${ARCHIVE}"
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
shasum -a 512 -c "${SUMFILE}" || die "Integrity check failed!"
echo

echo "Extracting shellcheck binary..."
# NOTE: Transforms tar paths into bin/shellcheck/.
tar --bzip2 -xf "${ARCHIVE}" --wildcards \
	--transform='s|.*/|bin/shellcheck/|' \
	./usr/bin/shellcheck \
	./usr/share/doc/*/LICENSE.bz2
chmod a+rX,a-w ./bin/shellcheck/*
