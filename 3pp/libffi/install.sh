#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX=$1
DEPS_PREFIX=$2

# generate configure, using libtool from DEPS_PREFIX
PATH=$DEPS_PREFIX/bin:$PATH ./autogen.sh

if [[ $_3PP_PLATFORM == mac* ]]; then
  python generate-darwin-source-and-headers.py --only-osx
fi

./configure --enable-static --disable-shared \
  --disable-docs \
  --host "$CROSS_TRIPLE" \
  --prefix "$PREFIX"
make install -j $(nproc)

# Some programs (like python) expect to be able to `#include <ffi.h>`, so
# create those symlinks.
mkdir $PREFIX/include
(cd $PREFIX/include && ln -s ../lib/libffi*/include/*.h ./)
(cd $PREFIX/lib && ln -s ../lib64/* ./)
