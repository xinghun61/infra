#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"
DEPS_PREFIX="$2"

export CCFLAGS="-I$DEPS_PREFIX/include"
export CFLAGS="-I$DEPS_PREFIX/include"
export LDFLAGS="-L$DEPS_PREFIX/lib"

./configure --enable-static --disable-shared \
  --prefix "$PREFIX" \
  --host "$CROSS_TRIPLE" \
  --with-curses
make install -j $(nproc)
(cd $PREFIX/include && ln -s ./readline/readline.h readline.h)
