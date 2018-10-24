#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -o pipefail

case $1 in
  help|-h|--help)
      cat <<'EOF'
This script is a thin wrapper for running the 3pp recipe locally.

By default this will:
  * Pull your logged-in email from `luci-auth` to derive a CIPD package
    prefix (if your email is `user@example.com`, this will try to upload
    to `experimental/user_at_example.com`)
  * [OS X only] Run `sudo -v` to refresh your sudo token; this is needed to
    run `xcode-select`.
  * Deletes the $WORKDIR/3pp subdirectory
  * Run the 3pp recipe in experimental mode using `//infra.git/.3pp_wd` as the
    default $WORKDIR

Options:
  * Set $WORKDIR to change what directory this uses for the recipe workdir.
  * Pass additional arguments to the script to pass directly to the
    recipe_engine. In particular:
      * 'to_build=["json","list","of","package","names"]' - This will allow
        you to restrict the packages that are built.
      * 'platform="linux-amd64"' - Allows you to select which CIPD platform
        you're targeting.

Tips:
  * When stuff goes wrong, it's very helpful to inspect the state of the
    $WORKDIR that's left behind.
  * If you end up uploading a bad package to your experimental prefix. You'll
    need to be a CIPD admin to delete them, but you can file a bug and ping
    iannucci@ or vadimsh@ to do this.

Notes:
  * You will need to give yourself CIPD writer access to the experimental prefix
    that this script derives from your email (e.g.
    `cipd acl-edit -writer email:user@example.com experimental/user_at_example.com`)
  * You need docker in $PATH if you're targetting any linux system (even if your
    host system is linux).
  * You may need to tell your docker service that it's OK to mount directories
    under $WORKDIR.
  * If your host runs a Case-Insensitive filesystem (OS X, Windows), and you
    target a linux platform, you should create a Case-Sensitive disk image and
    mount it to use as your workdir. Otherwise assumptions in some packages
    (like `cpython`) will be violated and they will have strange build failures.
  * If your host has path length issues (Windows), pick a short $WORKDIR (like
    `C:\wd`)
  * If your host has a very high inode count, be aware that docker passes inodes
    through to the container unchanged, and that 32-bit docker images have 32bit
    userland programs which cannot handle inodes >= 2**32. To resolve this,
    create a disk image and mount it to use as your $WORKDIR.
EOF

      exit 0
    ;;
esac

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
REPO=$(dirname $SCRIPT_DIR)
WORKDIR=${WORKDIR:-$REPO/.3pp_wd}

LOGIN_EMAIL=$(luci-auth info | awk '/Logged in/{gsub("\.$", "", $4); print $4}')
CIPD_EMAIL=$(sed 's/@/_at_/' <<<"$LOGIN_EMAIL")

if [[ $OSTYPE = darwin* ]]; then
  echo 'On OS X we need a fresh sudo token to run `xcode-select` as part of SDK setup.'
  sudo -v
fi

echo Using \$WORKDIR: $WORKDIR
echo Using \$CIPD_PREFIX: experimental/$CIPD_EMAIL

rm -rf $WORKDIR/3pp

set -x
$REPO/recipes/recipes.py run --workdir $WORKDIR \
  3pp \
  'package_locations=[{"repo": "file://'"$REPO"'", "ref": "HEAD", "subdir": "3pp"}]' \
  '$recipe_engine/runtime={"is_experimental": true}' \
  package_prefix=$CIPD_EMAIL \
  "$@"
