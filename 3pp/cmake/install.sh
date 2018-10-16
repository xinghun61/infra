#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -x
set -o pipefail

PREFIX="$1"

# Use the cmake in path to bootstrap cmak'ing cmake!
cmake \
  -GNinja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_USE_OPENSSL=OFF
# Our dockcross environment should automatically set the CMAKE toolchain to
# enable cross-compilation.

# Build all the stuffs.
ninja -j $(nproc) all

# Use the system cmake to actually do the install. Otherwise it will use the
# cmake binary we just built and fail when we're cross compiling.
cmake -P cmake_install.cmake
