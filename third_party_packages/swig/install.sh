#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"
DEPS="$2"

./autogen.sh
LDFLAGS="$LDFLAGS -L$DEPS/lib" ./configure \
  --enable-static --disable-shared \
  "--with-pcre-prefix=$DEPS" \
  "--prefix=$PREFIX" \
  "--host=$CROSS_TRIPLE"

make -j $(nproc)
DESTDIR="$PREFIX" make install -j $(nproc)
