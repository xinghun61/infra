#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"
DEPS="$2"

if [[ $OSTYPE == darwin* ]]; then
  EXTRA_CONFIG_ARGS=--with-darwinssl
else
  export LIBS='-ldl -lpthread'
  EXTRA_CONFIG_ARGS="--with-ssl=$DEPS"
fi

./configure --enable-static --disable-shared \
  --disable-ldap \
  --without-librtmp \
  --with-zlib="$DEPS" \
  --with-libidn2="$DEPS" \
  --prefix="$PREFIX" \
  --host="$CROSS_TRIPLE" \
  $EXTRA_CONFIG_ARGS
make install -j $(nproc)
