#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

cipd.exe ensure -root . -ensure-file - <<EOF
infra/7z/\${platform} version:9.20
EOF

./7z.exe x PortableGit*.exe "-o$PREFIX" -y

cd "$PREFIX"

# 7z.exe silent extraction does not support "RunProgram" installation header,
# which specifies the script to run after extraction. If the downloaded exe
# worked, it would run the post-install script. Here we hard-code the name of
# the file to run instead of extracting it from the downloaded archive because
# we already have to know too much about it (see below), so we have to break the
# API boundary anyway.
#
# We expect exit code 1. The post-script.bat tries to delete itself in
# the end and it always causes a non-zero exit code.
#
# Note that the post-install.bat also ignores exit codes of the *.post
# scripts that it runs, which is the important part.
# This has been the case for at least 2yrs
# https://github.com/git-for-windows/build-extra/commit/f1962c881ab18dd1ade087d2f5a7cac5b976f624
#
# BUG(WontFix): https://github.com/git-for-windows/git/issues/1147
./git-bash.exe --no-needs-console --hide --no-cd --command=post-install.bat || true

mingw_dir=mingw32
if [[ -d mingw64 ]]; then
  mingw_dir=mingw64
fi

./cmd/git.exe config -f $mingw_dir/etc/gitconfig core.autocrlf     false
./cmd/git.exe config -f $mingw_dir/etc/gitconfig core.filemode     false
./cmd/git.exe config -f $mingw_dir/etc/gitconfig core.preloadindex true
./cmd/git.exe config -f $mingw_dir/etc/gitconfig core.fscache      true
# Disable "Git Credential Manager", which pops modal dialogs when we don't
# want it. Kitchen will set credential.helper=luci anyway on bots.
./cmd/git.exe config -f $mingw_dir/etc/gitconfig --unset credential.helper


SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
cp $SCRIPT_DIR/profile.d.python.sh etc/profile.d/python.sh
cp $SCRIPT_DIR/profile.d.vpython.sh etc/profile.d/vpython.sh
