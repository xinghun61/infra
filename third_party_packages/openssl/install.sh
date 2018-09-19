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
  linux*)
    TARGET="linux-${CROSS_TRIPLE%%-*}"
    if [[ $CROSS_TRIPLE = aarch64* ]]; then
      # https://github.com/openssl/openssl/issues/1685
      ARGS=no-afalgeng
    fi
    ;;
  *)
    echo IDKWTF
    exit 1
esac

perl Configure --prefix="$PREFIX" no-shared $ARGS "$TARGET"

make -j $(nproc)
make install_sw
