#!/bin/bash -e
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Copies the requested shellcheck binary from the Chrome OS SDK public prebuilts
# and pins it as the new version in fetch_shellcheck.sh.
#
# After running this, a person with suitable permissions to the cipd
# infra/tricium/function/shellcheck package should be able to update like so:
#   1. Run ./fetch_shellcheck.sh to put the new version in bin/shellcheck
#   2. make testrun
#   3. Check test results.
#   4. Run 'cipd create -pkg-def cipd.yaml' to upload a new package version.

die() {
	echo "$1"
	exit 1
}

new_version="$1"
[[ -n "$new_version" ]] || die "Usage: $0 version"
old_version=$(grep '^VERSION' fetch_shellcheck.sh | cut -f2- -d=)

archive="shellcheck-${new_version}.tbz2"
sumfile="${archive}.sum"
old_archive="shellcheck-${old_version}.tbz2"
old_sumfile="${old_archive}.sum"

sdk_version=$(
	curl -s 'https://chromium.googlesource.com/chromiumos/overlays/chromiumos-overlay/+/master/chromeos/binhost/host/sdk_version.conf?format=TEXT' |
	base64 -d - |
	grep SDK_LATEST_VERSION |
        grep -o '[0-9.]*'
)
[[ -n "${sdk_version}" ]] || die "Unable to get current sdk version"
echo "Using sdk $sdk_version"

archive_url="https://storage.googleapis.com/chromeos-prebuilt/host/amd64/amd64-host/chroot-${sdk_version}/packages/dev-util/${archive}"
curl -f "${archive_url}" -o "${archive}" || die "Unable to download new shellcheck package"

shasum -a 512 "${archive}" > "${sumfile}"
rm "${archive}"

sed -i -e "s/^VERSION=.*/VERSION=${new_version}/" fetch_shellcheck.sh
sed -i -e "s/^SDK_VERSION=.*/SDK_VERSION=${sdk_version}/" fetch_shellcheck.sh

git add "${sumfile}"
git rm "${old_sumfile}"
git add fetch_shellcheck.sh
git commit -F- <<EOM
[tricium] Update shellcheck to ${new_version}

Binary downloaded from the Chrome OS SDK version ${sdk_version}.

Bug: <<REPLACE-ME>>
Test: <<REPLACE-ME>>
EOM

cat <<EOM
${archive} was downloaded from ${archive_url}

A git commit was created to update fetch_shellcheck.sh.  You need to amend this
commit with proper bug and test information, then upload it for review.
EOM
