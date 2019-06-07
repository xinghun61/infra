#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

CFLAGS=""
CPPFLAGS=""

case $OSTYPE in
  darwin*)
    TARGET=darwin64-x86_64-cc
    ;;
  linux*)
    case $CROSS_TRIPLE in
      arm-*) # explicitly pick armv4, the highest 32bit arm target available
        TARGET="linux-armv4"
        ;;
      mipsel-*)
        TARGET="linux-mips32"
        ;;
      *) # should apply to aarch64, mips32 and mips64
        TARGET="linux-${CROSS_TRIPLE%%-*}"
        ;;
    esac
    ;;
  *)
    echo IDKWTF
    exit 1
    ;;
esac

perl Configure -lpthread --prefix="$PREFIX" no-shared $ARGS "$TARGET"

make -j $(nproc)
make install_sw
