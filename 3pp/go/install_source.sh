#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

cd go

case $CROSS_TRIPLE in
  mipsel-*)  # Only support 32bit mips for now
    GOARCH=mipsle
    ;;
  *)
    echo "IDKWTF"
    exit 1
    ;;
esac

export GOOS=linux
export GOARCH
export CGO_ENABLED=0

(cd src && ./make.bash)

mkdir $PREFIX/{bin,pkg,src,lib}

SUFFIX=${GOOS}_${GOARCH}
cp -a bin/$SUFFIX/* $PREFIX/bin/
cp -a lib/*         $PREFIX/lib/
cp -a pkg/$SUFFIX/* $PREFIX/pkg/
cp -a src/*/        $PREFIX/src/
