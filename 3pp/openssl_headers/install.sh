#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

case $OSTYPE in
  darwin*)
    TARGET=darwin64-x86_64-cc
    ;;
  *)
    echo IDKWTF
    exit 1
esac

perl Configure --prefix="$PREFIX" no-shared $ARGS "$TARGET"

make -j $(nproc)
make install_sw
