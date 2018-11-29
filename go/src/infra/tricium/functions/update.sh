#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Helper utility to update analyzers.

# Usage.
if [ "$#" -eq 0 ] || [ "$1" == "--help" ] ; then
  echo "Usage: $ update.py directories..."
  echo "This only works on directories with both Makefile and cipd.yaml,"
  echo "where `make` builds the analyzer and `make clean` cleans up."
  exit 1
fi

set -x # Echo all commands as they are run.
set -u # Check for unset variables.
set -e # Exit on failure of a command.

function update {
  dir="$1"
  if [ ! -d "$dir" ]; then
    echo "$dir" is not a directory
    return
  fi
  pushd "$dir"
  make clean
  make
  out=$(cipd create -pkg-def=cipd.yaml)
  version=$(echo "$out" | grep Instance | sed 's/Instance: .*://')
  cipd set-ref "infra/tricium/function/$dir" -ref live -version "$version"
  make clean
  popd
}

# Iterate through input directories, updating each.
for dir in "$@"; do
  update "$dir"
done

exit 0
