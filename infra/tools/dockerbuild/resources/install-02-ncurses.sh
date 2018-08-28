#!/bin/bash
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Build and install a cross-compiled library.
#
# This script runs the standard "./configure", "make", "make install" workflow,
# which is generically useful for most libraries.
#
# This script consumes:
# - ARCHIVE_PATH is the path to the Perl archive file.
# - NO_HOST, if set, omits the "--host" argument from the configure script.

# Load our installation utility functions.
. /install-util.sh

if [ -z "${ARCHIVE_PATH}" ]; then
  echo "ERROR: Missing required environment."
  exit 1
fi

ROOT=${PWD}

# Unpack our archive and enter its base directory (whatever it is named).
ARCHIVE_PATH=$(basename ${ARCHIVE_PATH})
tar -xzf ${ARCHIVE_PATH}
cd $(get_archive_dir ${ARCHIVE_PATH})

# Build native programs and back them up
toggle_host
./configure --prefix=${CROSS_PREFIX}
make -j$(nproc)
cp -a progs progs.bak

toggle_cross
./configure --prefix=${CROSS_PREFIX} --host=${CROSS_TRIPLE}
make -j$(nproc)

# Restore native programs
rm -rf progs
mv progs.bak progs
find progs ! -name '*.*' -exec touch '{}' ';'

make install
